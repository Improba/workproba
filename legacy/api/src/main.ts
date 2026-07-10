import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import { urlencoded, json } from 'express';
import { NestExpressApplication } from '@nestjs/platform-express';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    cors: {
      origin: process.env.FRONTEND_URL,
      methods: 'GET,HEAD,PUT,PATCH,POST,DELETE',
      preflightContinue: false,
      optionsSuccessStatus: 204,
    },
  });
  app.use(json({ limit: '300mb' }));
  app.use(urlencoded({ extended: true, limit: '150mb' }));

  app.useGlobalPipes(
    new ValidationPipe({
      // automatically transform payloads (coming from the network)
      // to be objects typed according to their DTO classes
      // (= enforce type checking and type casting according to DTO validations)
      transform: true,
      // this will automatically remove non-whitelisted properties
      // (= remove propreties without any decorator in the validation class).
      whitelist: true,
      // when non-whitelisted properties are present,
      // stop the request from processing,
      // return an error response to the user
      // (used alongside `whilelist: true`)
      forbidNonWhitelisted: true,
      forbidUnknownValues: true,
      // TODO: to verify
      enableDebugMessages: true,
      // groups: []
      // disableErrorMessages: true,
      // validationError: {
      //   target: false,
      //   value: false,
      // },
    }),
  );

  // Configuration Swagger
  const config = new DocumentBuilder()
    .setTitle('API Documentation')
    .setDescription('Documentation de l\'API REST')
    .setVersion('1.0')
    .addBearerAuth(
      {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        name: 'JWT',
        description: 'Entrez votre token JWT',
        in: 'header',
      },
      'JWT-auth', // Ce nom sera utilisé pour référencer ce schéma de sécurité
    )
    .addTag('app', 'Endpoints généraux de l\'API')
    .addTag('auth', 'Endpoints d\'authentification')
    .addTag('users', 'Endpoints de gestion des utilisateurs')
    .addTag('admin', 'Endpoints d\'administration')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api-documentation', app, document, {
    swaggerOptions: {
      persistAuthorization: true, // Conserve le token JWT entre les rafraîchissements
    },
  });

  const server = await app.listen(3000);
  server.setTimeout(1000 * 60 * 5); // 5 min // 600,000=> 10Min, 1200,000=>20Min, 1800,000=>30Min
}
bootstrap();
