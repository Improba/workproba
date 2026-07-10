import { Injectable } from '@nestjs/common';

@Injectable()
export class AppService {
  getHello(): string {
    const version = process.env.npm_package_version;
    const appName = process.env.npm_package_name;
    return `<html><head><title>${appName}</title></head><body>${appName} version ${version}</body></html>`;
  }
}
