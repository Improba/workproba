import * as fs from 'fs';

export const createFolderIfNeeded = async (path: string) => {
  if (!(await exists(path))) {
    const splittedPath = path.split('/');
    let currentPath = '';
    for (const p of splittedPath) {
      currentPath += p + '/';
      if (p.length > 0 && p !== '.') {
        if (!(await exists(currentPath))) {
          await fs.promises.mkdir(currentPath);
        }
      }
    }
  }
};

export const removeFile = async (path: string) => {
  if (await exists(path)) {
    await fs.promises.rm(path);
  }
};

export const exists = async (path: string) =>
  !!(await fs.promises.stat(path).catch((e) => false));
