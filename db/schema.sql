\restrict dbmate

-- Dumped from database version 16.11 (Debian 16.11-1.pgdg12+1)
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunks (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    chunk_index integer NOT NULL,
    text text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(text, ''::text))) STORED,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    embedding public.vector(768),
    embedding_model text,
    embedded_at timestamp with time zone
);


--
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chunks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chunks_id_seq OWNED BY public.chunks.id;


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id bigint NOT NULL,
    conversation_key text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id bigint
);


--
-- Name: conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversations_id_seq OWNED BY public.conversations.id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id bigint NOT NULL,
    filename text NOT NULL,
    content_type text,
    size_bytes integer,
    sha256 text,
    extracted_text text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id bigint,
    deleted_at timestamp with time zone
);


--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: llm_models; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_models (
    id bigint NOT NULL,
    name text NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT false NOT NULL
);


--
-- Name: llm_models_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_models_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_models_id_seq OWNED BY public.llm_models.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id bigint NOT NULL,
    conversation_id bigint NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    sources jsonb DEFAULT '[]'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT messages_role_check CHECK ((role = ANY (ARRAY['system'::text, 'user'::text, 'assistant'::text])))
);


--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: model_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_settings (
    id smallint DEFAULT 1 NOT NULL,
    generation_model text NOT NULL,
    router_model text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT model_settings_id_check CHECK ((id = 1))
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    replaced_by_token_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    user_agent text,
    ip_address inet,
    CONSTRAINT refresh_tokens_token_hash_not_blank CHECK ((length(TRIM(BOTH FROM token_hash)) > 0))
);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT users_email_not_blank CHECK ((length(TRIM(BOTH FROM email)) > 0))
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: chunks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks ALTER COLUMN id SET DEFAULT nextval('public.chunks_id_seq'::regclass);


--
-- Name: conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations ALTER COLUMN id SET DEFAULT nextval('public.conversations_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: llm_models id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models ALTER COLUMN id SET DEFAULT nextval('public.llm_models_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: chunks chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_document_id_chunk_index_key UNIQUE (document_id, chunk_index);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_conversation_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_conversation_key_key UNIQUE (conversation_key);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: llm_models llm_models_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_name_key UNIQUE (name);


--
-- Name: llm_models llm_models_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: model_settings model_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_settings
    ADD CONSTRAINT model_settings_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: chunks_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunks_document_id_idx ON public.chunks USING btree (document_id);


--
-- Name: chunks_embedding_hnsw_cosine_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunks_embedding_hnsw_cosine_idx ON public.chunks USING hnsw (embedding public.vector_cosine_ops) WHERE (embedding IS NOT NULL);


--
-- Name: chunks_tsv_gin_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunks_tsv_gin_idx ON public.chunks USING gin (tsv);


--
-- Name: conversations_user_id_updated_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX conversations_user_id_updated_at_idx ON public.conversations USING btree (user_id, updated_at DESC) WHERE (user_id IS NOT NULL);


--
-- Name: conversations_user_updated_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX conversations_user_updated_idx ON public.conversations USING btree (user_id, updated_at DESC, id DESC);


--
-- Name: documents_active_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX documents_active_created_at_idx ON public.documents USING btree (created_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: documents_user_id_active_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX documents_user_id_active_created_at_idx ON public.documents USING btree (user_id, created_at DESC) WHERE ((user_id IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: documents_user_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX documents_user_id_created_at_idx ON public.documents USING btree (user_id, created_at DESC) WHERE (user_id IS NOT NULL);


--
-- Name: llm_models_enabled_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX llm_models_enabled_name_idx ON public.llm_models USING btree (name) WHERE is_enabled;


--
-- Name: llm_models_one_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX llm_models_one_active_idx ON public.llm_models USING btree (is_active) WHERE (is_active = true);


--
-- Name: messages_active_conversation_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_active_conversation_created_at_idx ON public.messages USING btree (conversation_id, created_at) WHERE (deleted_at IS NULL);


--
-- Name: messages_content_trgm_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_content_trgm_idx ON public.messages USING gin (lower(content) public.gin_trgm_ops);


--
-- Name: messages_conversation_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX messages_conversation_id_created_at_idx ON public.messages USING btree (conversation_id, created_at);


--
-- Name: refresh_tokens_expires_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX refresh_tokens_expires_at_idx ON public.refresh_tokens USING btree (expires_at);


--
-- Name: refresh_tokens_token_hash_uniq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX refresh_tokens_token_hash_uniq_idx ON public.refresh_tokens USING btree (token_hash);


--
-- Name: refresh_tokens_user_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX refresh_tokens_user_active_idx ON public.refresh_tokens USING btree (user_id, expires_at) WHERE (revoked_at IS NULL);


--
-- Name: users_email_lower_uniq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_email_lower_uniq_idx ON public.users USING btree (lower(email));


--
-- Name: chunks chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents documents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_replaced_by_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_replaced_by_token_id_fkey FOREIGN KEY (replaced_by_token_id) REFERENCES public.refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict dbmate


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20260208185243'),
    ('20260208193000'),
    ('20260209220000'),
    ('20260210220000'),
    ('20260211233000'),
    ('20260214163000'),
    ('20260214164000'),
    ('20260216163000'),
    ('20260216170000'),
    ('20260216183000'),
    ('20260216190000'),
    ('20260216193000'),
    ('20260216194500'),
    ('20260216200000'),
    ('20260216213000');
