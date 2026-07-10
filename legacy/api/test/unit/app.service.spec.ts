import { AppService } from 'src/app.service';

describe('AppService', () => {
  let service: AppService;

  beforeEach(() => {
    service = new AppService();
  });

  describe('getHello', () => {
    it('should return HTML with app name and version from env', () => {
      const originalName = process.env.npm_package_name;
      const originalVersion = process.env.npm_package_version;
      process.env.npm_package_name = 'test-api';
      process.env.npm_package_version = '1.2.3';

      const result = service.getHello();

      expect(result).toBe(
        '<html><head><title>test-api</title></head><body>test-api version 1.2.3</body></html>',
      );

      process.env.npm_package_name = originalName;
      process.env.npm_package_version = originalVersion;
    });
  });
});
