import { forwardRef, Module, OnModuleInit } from '@nestjs/common';
import { CronTasks } from './cron-tasks';

@Module({
  imports: [],
  controllers: [],
  providers: [CronTasks],
  exports: [],
})
export class CronTasksModule {}
