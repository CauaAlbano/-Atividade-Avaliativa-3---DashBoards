-- Camada OURO: esquema estrela (MySQL 8+)  |  Fato: fato_ocorrencia
CREATE DATABASE IF NOT EXISTS ocorrencias_aeronauticas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ocorrencias_aeronauticas;

DROP TABLE IF EXISTS fato_ocorrencia;
DROP TABLE IF EXISTS dim_cidade;
DROP TABLE IF EXISTS dim_uf;
DROP TABLE IF EXISTS dim_aerodromo;
DROP TABLE IF EXISTS dim_classificacao;
DROP TABLE IF EXISTS dim_tempo;

CREATE TABLE dim_classificacao (
  id_classificacao TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome VARCHAR(20) NOT NULL,
  PRIMARY KEY (id_classificacao),
  UNIQUE KEY uq_classificacao_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE dim_uf (
  id_uf SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sigla VARCHAR(15) NOT NULL,            -- inclui 'NÃO INFORMADO'
  regiao VARCHAR(12) NOT NULL,
  PRIMARY KEY (id_uf),
  UNIQUE KEY uq_uf_sigla (sigla)
) ENGINE=InnoDB;

CREATE TABLE dim_cidade (
  id_cidade INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome VARCHAR(80) NOT NULL,
  id_uf SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (id_cidade),
  UNIQUE KEY uq_cidade_uf (nome, id_uf),
  CONSTRAINT fk_cidade_uf FOREIGN KEY (id_uf) REFERENCES dim_uf (id_uf)
) ENGINE=InnoDB;

CREATE TABLE dim_aerodromo (
  id_aerodromo INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(20) NOT NULL,
  fora_aerodromo TINYINT(1) NOT NULL DEFAULT 0,   -- 1 = 'FAER' (fora de aeródromo)
  PRIMARY KEY (id_aerodromo),
  UNIQUE KEY uq_aerodromo_codigo (codigo)
) ENGINE=InnoDB;

CREATE TABLE dim_tempo (
  id_data INT NOT NULL,                  -- AAAAMMDD
  data DATE NOT NULL,
  ano SMALLINT NOT NULL,
  trimestre TINYINT NOT NULL,
  mes TINYINT NOT NULL,
  nome_mes VARCHAR(3) NOT NULL,
  dia TINYINT NOT NULL,
  dia_semana TINYINT NOT NULL,           -- 0 = segunda
  nome_dia_semana VARCHAR(3) NOT NULL,
  PRIMARY KEY (id_data),
  UNIQUE KEY uq_tempo_data (data)
) ENGINE=InnoDB;

CREATE TABLE fato_ocorrencia (
  codigo_ocorrencia INT NOT NULL,
  id_classificacao TINYINT UNSIGNED NOT NULL,
  id_cidade INT UNSIGNED NOT NULL,
  id_aerodromo INT UNSIGNED NOT NULL,
  id_data INT NOT NULL,
  hora_ocorrencia TIME NULL,
  hora_dia TINYINT NULL,
  latitude DECIMAL(12,9) NULL,
  longitude DECIMAL(12,9) NULL,
  saida_pista TINYINT(1) NOT NULL,
  aeronave_liberada TINYINT(1) NULL,
  status_investigacao VARCHAR(12) NOT NULL,
  investigacao_ativa TINYINT(1) NOT NULL,
  relatorio_numero VARCHAR(30) NULL,
  relatorio_publicado TINYINT(1) NOT NULL,
  data_publicacao DATE NULL,
  total_recomendacoes SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  total_aeronaves SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  flag_outlier_recomendacoes TINYINT(1) NOT NULL DEFAULT 0,
  flag_aeronaves_inconsistente TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (codigo_ocorrencia),
  KEY ix_fato_classificacao (id_classificacao),
  KEY ix_fato_cidade (id_cidade),
  KEY ix_fato_aerodromo (id_aerodromo),
  KEY ix_fato_data (id_data),
  CONSTRAINT fk_fato_classificacao FOREIGN KEY (id_classificacao) REFERENCES dim_classificacao (id_classificacao),
  CONSTRAINT fk_fato_cidade FOREIGN KEY (id_cidade) REFERENCES dim_cidade (id_cidade),
  CONSTRAINT fk_fato_aerodromo FOREIGN KEY (id_aerodromo) REFERENCES dim_aerodromo (id_aerodromo),
  CONSTRAINT fk_fato_data FOREIGN KEY (id_data) REFERENCES dim_tempo (id_data),
  CONSTRAINT ck_fato_lat CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT ck_fato_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB;
