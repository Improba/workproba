import { Migration } from '@mikro-orm/migrations';

export class Migration20251031163053_init extends Migration {

  override async up(): Promise<void> {
    this.addSql(`create table "user_jwt" ("id" bigserial primary key, "created_at" timestamptz null, "updated_at" timestamptz null, "deleted_at" timestamptz null, "username" varchar(255) not null, "password" varchar(255) not null, "activated" boolean not null default false, "activation_token" varchar(255) null, "last_reset_password_at" timestamptz null, "forget_password_token" varchar(255) null);`);
    this.addSql(`alter table "user_jwt" add constraint "user_jwt_username_unique" unique ("username");`);

    this.addSql(`create table "user" ("id" bigserial primary key, "created_at" timestamptz null, "updated_at" timestamptz null, "deleted_at" timestamptz null, "firstname" varchar(200) null, "lastname" varchar(200) null, "reset_password_ongoing" boolean not null default false, "roles" text[] not null default '{user}', "prefer_dark_theme" boolean not null default true, "user_jwt_id" bigint null);`);
    this.addSql(`create index "user_user_jwt_id_index" on "user" ("user_jwt_id");`);
    this.addSql(`alter table "user" add constraint "user_user_jwt_id_unique" unique ("user_jwt_id");`);

    this.addSql(`alter table "user" add constraint "user_user_jwt_id_foreign" foreign key ("user_jwt_id") references "user_jwt" ("id") on update cascade on delete cascade;`);
  }

  override async down(): Promise<void> {
    this.addSql(`alter table "user" drop constraint "user_user_jwt_id_foreign";`);

    this.addSql(`drop table if exists "user_jwt" cascade;`);

    this.addSql(`drop table if exists "user" cascade;`);
  }

}
