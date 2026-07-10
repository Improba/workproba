import { NestFactory } from '@nestjs/core';
import { INestApplicationContext } from '@nestjs/common';

//import { UserService } from '@users/services/user.service';

import { AppModule } from '../../app.module';

async function createUser(application: INestApplicationContext) {
  /*if (process.argv.length !== 5) {
    console.error('ERROR: wrong number of args');
    return;
  }

  const username = process.argv[3];
  const password = process.argv[4];

  const usersService = application.get(UserService);
  const users = await usersService.findWithUsername(<string>username);
  // console.log('Users found: ' + (<any>users).length);
  if (users && users.length === 0) {
    console.info('Creating the user...');
    await usersService.create({
      roles: [UserRoleEnum.User],
      userJwt: {
        username,
        password,
        activated: true,
      },
    });
  } else {
    console.info('The user already exists. Skip creation step.');
  }*/
}

async function createAdminUser(application: INestApplicationContext) {
  /*if (process.argv.length !== 5) {
    console.error('ERROR: wrong number of args');
    return;
  }

  const role = UserRoleEnum.Admin;
  const username = process.argv[3];
  const password = process.argv[4];

  const usersService = application.get(UserService);
  const users = await usersService.findWithUsername(<string>username);
  // console.log('Users found: ' + (<any>users).length);
  if (users && users.length === 0) {
    console.info('Creating the admin user...');
    await usersService.create({
      roles: [role],
      userJwt: {
        username,
        password,
        activated: true,
      },
    });
  } else {
    console.info('The admin user already exists. Skip creation step.');
  }*/
}

async function main(application: INestApplicationContext) {
  try {
    const arg2 = process.argv[2];
    if (arg2 === 'create-admin-user') {
      await createAdminUser(application);
    } else if (arg2 === 'create-user') {
      await createUser(application);
    } else {
      throw new Error(`ERROR: Argument 2 not recognized: ${arg2}`);
    }
  } catch (err: any) {
    console.error(err);
  }
}

async function bootstrap() {
  const application = await NestFactory.createApplicationContext(AppModule);

  await main(application);

  await application.close();
  process.exit(0);
}

bootstrap();
