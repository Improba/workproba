import axios from 'axios';
import * as fs from 'fs';
import * as Handlebars from 'handlebars';
import { vi } from 'vitest';

import { ExportService } from '@lib-improba/modules/exports/services/index.service';

vi.mock('axios');
vi.mock('fs', () => ({
  promises: {
    writeFile: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('ExportService', () => {
  let service: ExportService;

  beforeEach(() => {
    service = new ExportService();
    vi.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('toDocx', () => {
    it('should return stream when outputPath is not provided', async () => {
      const stream = { pipe: vi.fn() };
      vi.mocked(axios.post).mockResolvedValue({ data: stream });

      const result = await service.toDocx({
        html: '<p>Hello {{name}}</p>',
        variables: { name: 'World' },
      });

      expect(result).toBe(stream);
      expect(axios.post).toHaveBeenCalled();
    });

    it('should write file when outputPath is provided', async () => {
      const stream = { data: 'docx-stream' };
      vi.mocked(axios.post).mockResolvedValue({ data: stream });

      const path = await service.toDocx({
        html: '<p>Test</p>',
        outputPath: '/tmp/out.docx',
      });

      expect(path).toBe('/tmp/out.docx');
      expect(fs.promises.writeFile).toHaveBeenCalledWith(
        '/tmp/out.docx',
        stream,
      );
    });
  });

  describe('toPdf', () => {
    it('should compile variables in html', async () => {
      const compileSpy = vi.spyOn(Handlebars, 'compile');
      vi.mocked(axios.post).mockResolvedValue({ data: 'pdf-stream' });

      await service.toPdf({
        html: '<p>{{greeting}}</p>',
        variables: { greeting: 'Hi' },
      });

      expect(compileSpy).toHaveBeenCalled();
      compileSpy.mockRestore();
    });
  });
});
