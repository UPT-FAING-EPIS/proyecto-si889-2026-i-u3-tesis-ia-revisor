create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  pdf_storage_path text,
  pdf_size_bytes bigint,
  pdf_mime_type text,
  created_at timestamptz not null default now()
);

alter table if exists public.documents
  add column if not exists pdf_storage_path text;

alter table if exists public.documents
  add column if not exists pdf_size_bytes bigint;

alter table if exists public.documents
  add column if not exists pdf_mime_type text;

create table if not exists public.document_chunks (
  id bigserial primary key,
  document_id uuid not null references public.documents(id) on delete cascade,
  content text not null,
  embedding vector(3072) not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid references public.documents(id) on delete cascade,
  mode text not null default 'pdf_chat' check (mode in ('pdf_chat', 'thesis_review', 'thesis_plan', 'thesis')),
  title text not null default 'Nuevo chat',
  faculty_id text,
  career_id text,
  source_chat_session_id uuid references public.chat_sessions(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz
);

alter table if exists public.chat_sessions
  alter column document_id drop not null;

alter table if exists public.chat_sessions
  drop constraint if exists chat_sessions_mode_check;

alter table if exists public.chat_sessions
  add constraint chat_sessions_mode_check
  check (mode in ('pdf_chat', 'thesis_review', 'thesis_plan', 'thesis'));

alter table if exists public.chat_sessions
  add column if not exists faculty_id text,
  add column if not exists career_id text,
  add column if not exists source_chat_session_id uuid;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'chat_sessions_source_chat_session_id_fkey'
      and conrelid = 'public.chat_sessions'::regclass
  ) then
    alter table public.chat_sessions
      add constraint chat_sessions_source_chat_session_id_fkey
      foreign key (source_chat_session_id)
      references public.chat_sessions(id)
      on delete set null;
  end if;
end $$;

create table if not exists public.chat_messages (
  id bigserial primary key,
  chat_session_id uuid not null references public.chat_sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.user_academic_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  faculty_id text not null,
  career_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.thesis_problem_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  problem text not null,
  search_query text,
  status text not null default 'pending' check (status in ('pending', 'running', 'completed', 'failed')),
  total_sources integer not null default 5 check (total_sources >= 0),
  found_sources integer not null default 0 check (found_sources >= 0),
  progress_percent integer not null default 0 check (progress_percent >= 0 and progress_percent <= 100),
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  delimitation_status text check (delimitation_status in ('pending', 'running', 'completed', 'failed')),
  delimitation_text text,
  delimitation_error_message text,
  chat_session_id uuid references public.chat_sessions(id) on delete set null,
  job_type text not null default 'problem_sources' check (job_type in ('problem_sources', 'auto_thesis_plan', 'auto_thesis')),
  selected_problem jsonb,
  ai_provider text,
  ai_model text,
  faculty_id text,
  career_id text,
  progress_label text,
  started_at timestamptz,
  completed_at timestamptz,
  notified_at timestamptz,
  pdf_storage_path text,
  pdf_filename text,
  pdf_size_bytes bigint,
  pdf_mime_type text,
  pdf_generated_at timestamptz
);

alter table if exists public.thesis_problem_jobs
  add column if not exists job_type text not null default 'problem_sources';

alter table if exists public.thesis_problem_jobs
  drop constraint if exists thesis_problem_jobs_job_type_check;

alter table if exists public.thesis_problem_jobs
  add constraint thesis_problem_jobs_job_type_check
  check (job_type in ('problem_sources', 'auto_thesis_plan', 'auto_thesis'));

alter table if exists public.thesis_problem_jobs
  add column if not exists selected_problem jsonb,
  add column if not exists ai_provider text,
  add column if not exists ai_model text,
  add column if not exists faculty_id text,
  add column if not exists career_id text,
  add column if not exists progress_label text,
  add column if not exists started_at timestamptz,
  add column if not exists completed_at timestamptz,
  add column if not exists notified_at timestamptz,
  add column if not exists pdf_storage_path text,
  add column if not exists pdf_filename text,
  add column if not exists pdf_size_bytes bigint,
  add column if not exists pdf_mime_type text,
  add column if not exists pdf_generated_at timestamptz;

create index if not exists idx_documents_user_id on public.documents(user_id);
create index if not exists idx_document_chunks_document_id on public.document_chunks(document_id);
create index if not exists idx_chat_sessions_user_document_mode
  on public.chat_sessions(user_id, document_id, mode);
create index if not exists idx_chat_sessions_document_id
  on public.chat_sessions(document_id);
create index if not exists idx_chat_sessions_user_mode
  on public.chat_sessions(user_id, mode, created_at desc);
create index if not exists idx_chat_sessions_user_academic
  on public.chat_sessions(user_id, faculty_id, career_id);
create index if not exists idx_chat_sessions_source_chat_session_id
  on public.chat_sessions(source_chat_session_id);
create index if not exists idx_chat_sessions_last_message_at
  on public.chat_sessions(last_message_at desc nulls last, created_at desc);
create index if not exists idx_chat_messages_chat_session_id
  on public.chat_messages(chat_session_id, created_at);
create index if not exists idx_user_academic_profiles_faculty_career
  on public.user_academic_profiles(faculty_id, career_id);
create index if not exists idx_thesis_problem_jobs_user_type_status
  on public.thesis_problem_jobs(user_id, job_type, status, created_at desc);
create index if not exists idx_thesis_problem_jobs_auto_unnotified
  on public.thesis_problem_jobs(user_id, completed_at desc)
  where job_type = 'auto_thesis_plan'
    and status = 'completed'
    and notified_at is null;
create index if not exists idx_thesis_jobs_auto_unnotified
  on public.thesis_problem_jobs(user_id, completed_at desc)
  where job_type = 'auto_thesis'
    and status = 'completed'
    and notified_at is null;

create index if not exists idx_document_chunks_embedding
  on public.document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function public.touch_chat_session_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_chat_session_updated_at on public.chat_sessions;
create trigger set_chat_session_updated_at
before update on public.chat_sessions
for each row
execute function public.touch_chat_session_updated_at();

create or replace function public.touch_user_academic_profile_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_user_academic_profile_updated_at on public.user_academic_profiles;
create trigger set_user_academic_profile_updated_at
before update on public.user_academic_profiles
for each row
execute function public.touch_user_academic_profile_updated_at();

create or replace function public.touch_chat_session_on_message_insert()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  update public.chat_sessions
  set
    updated_at = now(),
    last_message_at = now()
  where id = new.chat_session_id;
  return new;
end;
$$;

drop trigger if exists set_chat_session_last_message_on_insert on public.chat_messages;
create trigger set_chat_session_last_message_on_insert
after insert on public.chat_messages
for each row
execute function public.touch_chat_session_on_message_insert();

create or replace function public.match_document_chunks(
  match_document_id uuid,
  query_embedding vector(3072),
  match_count integer default 5
)
returns table (
  id bigint,
  document_id uuid,
  content text,
  similarity double precision
)
language sql
stable
set search_path = public
as $$
  select
    c.id,
    c.document_id,
    c.content,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.document_chunks c
  where c.document_id = match_document_id
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.user_academic_profiles enable row level security;
alter table public.thesis_problem_jobs enable row level security;

drop policy if exists documents_select_own on public.documents;
create policy documents_select_own
  on public.documents
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists documents_insert_own on public.documents;
create policy documents_insert_own
  on public.documents
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists documents_update_own on public.documents;
create policy documents_update_own
  on public.documents
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists documents_delete_own on public.documents;
create policy documents_delete_own
  on public.documents
  for delete
  using ((select auth.uid()) = user_id);

drop policy if exists chunks_select_owner on public.document_chunks;
create policy chunks_select_owner
  on public.document_chunks
  for select
  using (
    exists (
      select 1
      from public.documents d
      where d.id = document_chunks.document_id
        and d.user_id = (select auth.uid())
    )
  );

drop policy if exists chunks_insert_owner on public.document_chunks;
create policy chunks_insert_owner
  on public.document_chunks
  for insert
  with check (
    exists (
      select 1
      from public.documents d
      where d.id = document_chunks.document_id
        and d.user_id = (select auth.uid())
    )
  );

drop policy if exists chunks_delete_owner on public.document_chunks;
create policy chunks_delete_owner
  on public.document_chunks
  for delete
  using (
    exists (
      select 1
      from public.documents d
      where d.id = document_chunks.document_id
        and d.user_id = (select auth.uid())
    )
  );

drop policy if exists chat_sessions_select_own on public.chat_sessions;
create policy chat_sessions_select_own
  on public.chat_sessions
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists chat_sessions_insert_own on public.chat_sessions;
create policy chat_sessions_insert_own
  on public.chat_sessions
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists chat_sessions_update_own on public.chat_sessions;
create policy chat_sessions_update_own
  on public.chat_sessions
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists chat_sessions_delete_own on public.chat_sessions;
create policy chat_sessions_delete_own
  on public.chat_sessions
  for delete
  using ((select auth.uid()) = user_id);

drop policy if exists chat_messages_select_owner on public.chat_messages;
create policy chat_messages_select_owner
  on public.chat_messages
  for select
  using (
    exists (
      select 1
      from public.chat_sessions s
      where s.id = chat_messages.chat_session_id
        and s.user_id = (select auth.uid())
    )
  );

drop policy if exists chat_messages_insert_owner on public.chat_messages;
create policy chat_messages_insert_owner
  on public.chat_messages
  for insert
  with check (
    exists (
      select 1
      from public.chat_sessions s
      where s.id = chat_messages.chat_session_id
        and s.user_id = (select auth.uid())
    )
  );

drop policy if exists user_academic_profiles_select_own on public.user_academic_profiles;
create policy user_academic_profiles_select_own
  on public.user_academic_profiles
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists user_academic_profiles_insert_own on public.user_academic_profiles;
create policy user_academic_profiles_insert_own
  on public.user_academic_profiles
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists user_academic_profiles_update_own on public.user_academic_profiles;
create policy user_academic_profiles_update_own
  on public.user_academic_profiles
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists thesis_problem_jobs_select_own on public.thesis_problem_jobs;
create policy thesis_problem_jobs_select_own
  on public.thesis_problem_jobs
  for select
  using ((select auth.uid()) = user_id);

drop policy if exists thesis_problem_jobs_insert_own on public.thesis_problem_jobs;
create policy thesis_problem_jobs_insert_own
  on public.thesis_problem_jobs
  for insert
  with check ((select auth.uid()) = user_id);

drop policy if exists thesis_problem_jobs_update_own on public.thesis_problem_jobs;
create policy thesis_problem_jobs_update_own
  on public.thesis_problem_jobs
  for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists thesis_problem_jobs_delete_own on public.thesis_problem_jobs;
create policy thesis_problem_jobs_delete_own
  on public.thesis_problem_jobs
  for delete
  using ((select auth.uid()) = user_id);

drop policy if exists chat_messages_delete_owner on public.chat_messages;
create policy chat_messages_delete_owner
  on public.chat_messages
  for delete
  using (
    exists (
      select 1
      from public.chat_sessions s
      where s.id = chat_messages.chat_session_id
        and s.user_id = (select auth.uid())
    )
  );

-- Si cambias SUPABASE_STORAGE_BUCKET en .env, actualiza tambien el nombre en las
-- politicas de storage de este bloque.
insert into storage.buckets (id, name, public)
values ('thesis-documents', 'thesis-documents', false)
on conflict (id) do nothing;

drop policy if exists thesis_documents_select_own on storage.objects;
create policy thesis_documents_select_own
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'thesis-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists thesis_documents_insert_own on storage.objects;
create policy thesis_documents_insert_own
  on storage.objects
  for insert
  to authenticated
  with check (
    bucket_id = 'thesis-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists thesis_documents_update_own on storage.objects;
create policy thesis_documents_update_own
  on storage.objects
  for update
  to authenticated
  using (
    bucket_id = 'thesis-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'thesis-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists thesis_documents_delete_own on storage.objects;
create policy thesis_documents_delete_own
  on storage.objects
  for delete
  to authenticated
  using (
    bucket_id = 'thesis-documents'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
