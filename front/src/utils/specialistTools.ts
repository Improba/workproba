import type { ManagedConnector, PersonaInfo } from '@services/aiSidecar';

export interface SpecialistToolRef {
  connector_id: string;
  tool: string;
}

export interface SpecialistToolsConfig {
  allowed?: SpecialistToolRef[];
  forbidden?: SpecialistToolRef[];
}

function parseToolRef(value: unknown): SpecialistToolRef | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const connectorId = String(record.connector_id ?? '').trim();
  const tool = String(record.tool ?? '').trim();
  if (!connectorId || !tool) return null;
  return { connector_id: connectorId, tool };
}

function parseToolRefList(value: unknown): SpecialistToolRef[] {
  if (!Array.isArray(value)) return [];
  const refs: SpecialistToolRef[] = [];
  for (const item of value) {
    const parsed = parseToolRef(item);
    if (parsed) refs.push(parsed);
  }
  return refs;
}

export function parseSpecialistTools(raw: unknown): SpecialistToolsConfig | null {
  if (!raw || typeof raw !== 'object') return null;
  const record = raw as Record<string, unknown>;
  const allowed = parseToolRefList(record.allowed);
  const forbidden = parseToolRefList(record.forbidden);
  if (!allowed.length && !forbidden.length) return null;
  return { allowed, forbidden };
}

export function isBusinessAgent(persona: PersonaInfo): boolean {
  return persona.is_business_agent === true;
}

export function specialistAllowedTools(persona: PersonaInfo): SpecialistToolRef[] {
  return parseSpecialistTools(persona.tools)?.allowed ?? [];
}

export function resolveManagedToolEffect(
  connectors: ManagedConnector[],
  ref: SpecialistToolRef,
): string | null {
  const connector = connectors.find((item) => item.id === ref.connector_id);
  if (!connector?.tools?.length) return null;
  const match = connector.tools.find((tool) => tool.name === ref.tool);
  const effect = match?.effect?.trim();
  return effect || null;
}

export function toolRefKey(ref: SpecialistToolRef): string {
  return `${ref.connector_id}::${ref.tool}`;
}
