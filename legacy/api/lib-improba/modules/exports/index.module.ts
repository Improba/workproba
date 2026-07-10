import { forwardRef, Module, OnModuleInit } from '@nestjs/common';
import { ExportService } from './services/index.service';
import { BaseModule } from '@lib-improba/base/base.module';

@Module({
  imports: [
    BaseModule.forCustomRepository([]),
  ],
  controllers: [],
  providers: [ExportService],
  exports: [ExportService],
})
export class ExportsModule implements OnModuleInit {
  constructor(
  ) {}

  async onModuleInit() {
    console.info(`Exports module initialization...`);
    console.info(`Exports module initialized`);
  }
}
