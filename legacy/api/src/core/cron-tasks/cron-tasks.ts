import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@mikro-orm/nestjs';
import { Cron, Interval } from '@nestjs/schedule';

@Injectable()
export class CronTasks {
  // This used to avoir running the task if the previous one is still running
  private _ongoingSayHi = false;

  constructor() {}

  /**
   * Will be run every 5 seconds
   */
  // @Cron('*/5 * * * * *') // Alternative syntax
  /* @Interval(5 * 1000)
  async sayHi() {
    if (this._ongoingSayHi === false) {
      this._ongoingSayHi = true;
      try {
        // Try catch are required to ensure the _ongoingSayHi is always set to false
        // console.log('Say Hi');
      } catch (err: any) {
        console.error(err);
      }
      this._ongoingSayHi = false;
    }
  } */
  
}
