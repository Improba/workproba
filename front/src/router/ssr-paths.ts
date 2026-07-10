/**
 * SSR path introspection for the SPA-shell fallback.
 *
 * Walks the router's `RouteRecordRaw` tree and collects the set of paths
 * that should be server-side rendered. Everything else (authenticated
 * routes, dynamic routes, unknown paths, internal routes) is served as a
 * CSR shell and rendered in the browser.
 *
 * A route is considered CSR (excluded from SSR) when it, or any ancestor,
 * matches any of:
 *   - `meta.ssr === false`   (explicit opt-out)
 *   - `meta.requiresAuth === true`
 *   - `meta.auth === true`
 *
 * Redirect-only routes (a `redirect` but no `component`) and routes with a
 * dynamic path segment (`:` or `*`) are also excluded.
 */
import type { RouteRecordRaw } from 'vue-router';

type MetaRecord = Record<string, unknown> | undefined;

function isDynamicPath(path: string): boolean {
  return path.includes(':') || path.includes('*');
}

function isCsrMeta(meta: MetaRecord, inherited: boolean): boolean {
  if (inherited) return true;
  if (!meta) return false;
  return meta.ssr === false || meta.requiresAuth === true || meta.auth === true;
}

function joinPath(parent: string, segment: string): string {
  if (!segment) return parent || '/';
  const cleanSegment = segment.startsWith('/') ? segment : `/${segment}`;
  if (parent === '/' || parent === '') return cleanSegment;
  return `${parent}${cleanSegment}`;
}

function walk(
  routes: RouteRecordRaw[],
  parentPath: string,
  csrInherited: boolean,
  out: Set<string>,
): void {
  for (const route of routes) {
    const fullPath = joinPath(parentPath, route.path ?? '');
    const csr = isCsrMeta(route.meta as MetaRecord, csrInherited);
    const hasComponent = !!route.component;
    const hasRedirect = !!route.redirect;
    const isInternal = fullPath.startsWith('/__');

    if (
      hasComponent &&
      !hasRedirect &&
      !isInternal &&
      !isDynamicPath(fullPath) &&
      !csr
    ) {
      addPathVariants(out, fullPath);
    }

    if (route.children?.length) {
      walk(route.children, fullPath, csr, out);
    }
  }
}

function addPathVariants(set: Set<string>, path: string): void {
  set.add(path);
  if (path.endsWith('/') && path.length > 1) {
    set.add(path.slice(0, -1));
  } else if (path !== '/') {
    set.add(`${path}/`);
  }
}

export function collectSsrPaths(routes: RouteRecordRaw[]): Set<string> {
  const out = new Set<string>();
  walk(routes, '', false, out);
  return out;
}

export function matchesPathSet(pathName: string, paths: Set<string>): boolean {
  const trimmed =
    pathName.endsWith('/') && pathName.length > 1 ? pathName.slice(0, -1) : pathName;
  return paths.has(pathName) || paths.has(trimmed) || paths.has(`${trimmed}/`);
}
