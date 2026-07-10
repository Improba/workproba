import { Migration } from '@mikro-orm/migrations';

export class Migration20260708161500_workproba_core_skeleton extends Migration {
  override async up(): Promise<void> {
    this.addSql(`create extension if not exists vector;`);

    this.addSql(`
      create table "tenant" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "name" varchar(200) not null,
        "slug" varchar(120) not null,
        "is_active" boolean not null default true
      );
    `);
    this.addSql(`create unique index "tenant_slug_unique" on "tenant" ("slug");`);
    this.addSql(`create index "tenant_slug_index" on "tenant" ("slug");`);

    this.addSql(`
      create table "project" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "tenant_id" bigint not null,
        "name" varchar(200) not null,
        "slug" varchar(120) not null,
        "description" text null,
        "object_storage_prefix" varchar(500) null
      );
    `);
    this.addSql(`create index "project_tenant_id_index" on "project" ("tenant_id");`);
    this.addSql(`create index "project_slug_index" on "project" ("slug");`);
    this.addSql(`alter table "project" add constraint "project_tenant_id_foreign" foreign key ("tenant_id") references "tenant" ("id") on update cascade;`);

    this.addSql(`
      create table "document" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "project_id" bigint not null,
        "filename" varchar(255) not null,
        "mime_type" varchar(120) null,
        "size_bytes" bigint not null,
        "storage_path" varchar(1000) not null,
        "status" text not null default 'uploaded',
        "metadata" jsonb null,
        "indexed_at" timestamptz null
      );
    `);
    this.addSql(`create index "document_project_id_index" on "document" ("project_id");`);
    this.addSql(`alter table "document" add constraint "document_project_id_foreign" foreign key ("project_id") references "project" ("id") on update cascade;`);

    this.addSql(`
      create table "session" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "project_id" bigint not null,
        "title" varchar(255) null,
        "metadata" jsonb null
      );
    `);
    this.addSql(`create index "session_project_id_index" on "session" ("project_id");`);
    this.addSql(`alter table "session" add constraint "session_project_id_foreign" foreign key ("project_id") references "project" ("id") on update cascade;`);

    this.addSql(`
      create table "message" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "session_id" bigint not null,
        "role" text not null,
        "content" text not null,
        "parent_id" bigint null,
        "provider_message_id" varchar(120) null,
        "metadata" jsonb null
      );
    `);
    this.addSql(`create index "message_session_id_index" on "message" ("session_id");`);
    this.addSql(`create index "message_parent_id_index" on "message" ("parent_id");`);
    this.addSql(`alter table "message" add constraint "message_session_id_foreign" foreign key ("session_id") references "session" ("id") on update cascade;`);
    this.addSql(`alter table "message" add constraint "message_parent_id_foreign" foreign key ("parent_id") references "message" ("id") on update cascade on delete set null;`);

    this.addSql(`
      create table "llm_provider" (
        "id" bigserial primary key,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "name" varchar(120) not null,
        "kind" text not null,
        "base_url" varchar(500) null,
        "api_key" varchar(500) null,
        "default_model" varchar(200) null,
        "embedding_model" varchar(200) null,
        "is_active" boolean not null default true,
        "tenant_id" bigint null
      );
    `);
    this.addSql(`create index "llm_provider_tenant_id_index" on "llm_provider" ("tenant_id");`);
    this.addSql(`alter table "llm_provider" add constraint "llm_provider_tenant_id_foreign" foreign key ("tenant_id") references "tenant" ("id") on update cascade on delete set null;`);

    this.addSql(`
      create table "embedding" (
        "id" bigserial not null,
        "created_at" timestamptz null,
        "updated_at" timestamptz null,
        "deleted_at" timestamptz null,
        "tenant_id" bigint not null,
        "project_id" bigint not null,
        "document_id" bigint null,
        "chunk_index" integer not null,
        "content" text not null,
        "vector" vector(1536) not null,
        primary key ("tenant_id", "id")
      ) partition by list ("tenant_id");
    `);
    this.addSql(`create table "embedding_default" partition of "embedding" default;`);
    this.addSql(`create index "embedding_tenant_id_index" on "embedding" ("tenant_id");`);
    this.addSql(`create index "embedding_project_id_index" on "embedding" ("project_id");`);
    this.addSql(`create index "embedding_document_id_index" on "embedding" ("document_id");`);
    this.addSql(`create index "embedding_vector_cosine_index" on "embedding" using hnsw ("vector" vector_cosine_ops);`);
    this.addSql(`alter table "embedding" add constraint "embedding_tenant_id_foreign" foreign key ("tenant_id") references "tenant" ("id") on update cascade;`);
    this.addSql(`alter table "embedding" add constraint "embedding_project_id_foreign" foreign key ("project_id") references "project" ("id") on update cascade;`);
    this.addSql(`alter table "embedding" add constraint "embedding_document_id_foreign" foreign key ("document_id") references "document" ("id") on update cascade on delete set null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop table if exists "embedding" cascade;`);
    this.addSql(`drop table if exists "llm_provider" cascade;`);
    this.addSql(`drop table if exists "message" cascade;`);
    this.addSql(`drop table if exists "session" cascade;`);
    this.addSql(`drop table if exists "document" cascade;`);
    this.addSql(`drop table if exists "project" cascade;`);
    this.addSql(`drop table if exists "tenant" cascade;`);
  }
}
