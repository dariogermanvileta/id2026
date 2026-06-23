-- ============================================================
-- I+D 2026 - Esquema PostgreSQL
-- Protergium / Agro Sciences
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── TABLAS MAESTRAS ─────────────────────────────────────────

CREATE TABLE cepas (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,   -- ARA6, TH10, GI9, T2, E109…
    nombre      VARCHAR(200) NOT NULL,          -- Trichoderma harzianum 10
    descripcion TEXT,
    activa      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE medios_cultivo (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,   -- RAMO1, BRA3, PDA…
    nombre      VARCHAR(100) NOT NULL,
    descripcion TEXT,
    activo      BOOLEAN DEFAULT TRUE
);

CREATE TABLE reactores (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(20) UNIQUE NOT NULL,   -- REACTOR1…REACTOR6, PLANTA_PILOTO
    nombre      VARCHAR(100) NOT NULL,
    volumen_max NUMERIC(10,2),                 -- litros
    ubicacion   VARCHAR(100),
    activo      BOOLEAN DEFAULT TRUE
);

CREATE TABLE usuarios (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,
    iniciales   VARCHAR(5) UNIQUE NOT NULL,    -- DV, AR, IC…
    email       VARCHAR(200) UNIQUE,
    rol         VARCHAR(20) DEFAULT 'operador' CHECK (rol IN ('admin','operador','visor')),
    password_hash VARCHAR(200),
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE presentaciones (
    id      SERIAL PRIMARY KEY,
    codigo  VARCHAR(50) UNIQUE NOT NULL,
    nombre  VARCHAR(100) NOT NULL
);

CREATE TABLE destinos (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(50) UNIQUE NOT NULL   -- Producción, Ensayos campo, I+D, Descarte, Otros
);

-- ─── PEDIDOS DE MUESTRAS ─────────────────────────────────────

CREATE TABLE pedidos_muestras (
    id              SERIAL PRIMARY KEY,
    numero          INTEGER UNIQUE NOT NULL,   -- correlativo (arranca en 185)
    fecha_emision   DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_entrega   DATE,
    solicitante     VARCHAR(200) NOT NULL,
    motivo          VARCHAR(200),
    retira          BOOLEAN DEFAULT FALSE,
    envia           BOOLEAN DEFAULT FALSE,
    estado          VARCHAR(30) DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','en_proceso','control_calidad','entregado','cancelado')),
    responsable_id  INTEGER REFERENCES usuarios(id),
    observaciones   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pedido_muestras_items (
    id              SERIAL PRIMARY KEY,
    pedido_id       INTEGER NOT NULL REFERENCES pedidos_muestras(id) ON DELETE CASCADE,
    rotulo          VARCHAR(100) NOT NULL,
    volumen_l       NUMERIC(10,3),
    presentacion_id INTEGER REFERENCES presentaciones(id),
    observaciones   TEXT,
    -- resultados de CC
    recuento        NUMERIC(15,2),
    pureza          VARCHAR(10) CHECK (pureza IN ('SI','NO',NULL)),
    responsable_cc  INTEGER REFERENCES usuarios(id)
);

-- ─── EXPERIMENTOS / BATCH ────────────────────────────────────

CREATE TABLE experimentos (
    id              SERIAL PRIMARY KEY,
    lote            VARCHAR(100) UNIQUE NOT NULL,  -- generado: TH10-RAMO1-20260623-001
    nombre          VARCHAR(200),
    cepa_id         INTEGER NOT NULL REFERENCES cepas(id),
    medio_id        INTEGER REFERENCES medios_cultivo(id),
    reactor_id      INTEGER REFERENCES reactores(id),
    volumen_l       NUMERIC(10,2),
    cultivo_objetivo VARCHAR(50),                  -- Producción, Ensayo campo, I+D…
    producto_final  VARCHAR(100),                  -- BIOFIX…
    temp_objetivo   NUMERIC(5,1),                  -- °C
    ph_objetivo     NUMERIC(4,2),
    -- trazabilidad de lotes
    lote_medio      VARCHAR(100),
    lote_sales      VARCHAR(100),
    lote_preinoculo VARCHAR(100),
    lote_inoculo    VARCHAR(100),
    -- metadatos
    responsable_id  INTEGER REFERENCES usuarios(id),
    destino_id      INTEGER REFERENCES destinos(id),
    fecha_siembra   DATE,
    estado          VARCHAR(30) DEFAULT 'activo'
                    CHECK (estado IN ('activo','completado','descartado')),
    notas           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- mediciones durante el proceso
CREATE TABLE experimento_mediciones (
    id              SERIAL PRIMARY KEY,
    experimento_id  INTEGER NOT NULL REFERENCES experimentos(id) ON DELETE CASCADE,
    fecha_hora      TIMESTAMPTZ DEFAULT NOW(),
    temperatura     NUMERIC(5,1),
    ph              NUMERIC(4,2),
    do_value        NUMERIC(8,4),
    observaciones   TEXT,
    operador_id     INTEGER REFERENCES usuarios(id)
);

-- ─── CONTROL DE CALIDAD MICROBIOLÓGICO ───────────────────────

CREATE TABLE cc_microbiologico (
    id              SERIAL PRIMARY KEY,
    -- vinculación (opcional a experimento o pedido)
    experimento_id  INTEGER REFERENCES experimentos(id),
    pedido_id       INTEGER REFERENCES pedidos_muestras(id),
    -- datos del lote
    cepa_id         INTEGER REFERENCES cepas(id),
    medio_id        INTEGER REFERENCES medios_cultivo(id),
    lote_medio      VARCHAR(100),
    lote_sales      VARCHAR(100),
    lote_preinoculo VARCHAR(100),
    lote_inoculo    VARCHAR(100),
    -- parámetros medidos
    ph              NUMERIC(4,2),
    do_value        NUMERIC(8,4),
    pureza          VARCHAR(10) CHECK (pureza IN ('SI','NO')),
    -- UFC/mL - recuentos crudos (hasta 10 lecturas)
    recuentos_ufc   NUMERIC[] DEFAULT '{}',        -- array de lecturas de placa
    factor_ufc      NUMERIC(6,2) DEFAULT 2.5,
    dilucion_ufc    NUMERIC(15,0) DEFAULT 1000000,
    ufc_calculado   NUMERIC(20,2),                 -- resultado = promedio * factor * dilución
    -- conidios
    recuentos_conidios_1_10  NUMERIC[] DEFAULT '{}',
    recuentos_conidios_1_20  NUMERIC[] DEFAULT '{}',
    conidios_1_10_calculado  NUMERIC(20,2),
    conidios_1_20_calculado  NUMERIC(20,2),
    dilucion_conidios        NUMERIC(15,0) DEFAULT 100000000,
    vol_conidios             NUMERIC(6,3) DEFAULT 0.1,
    -- metadatos
    fecha           DATE DEFAULT CURRENT_DATE,
    responsable_id  INTEGER REFERENCES usuarios(id),
    destino_id      INTEGER REFERENCES destinos(id),
    observaciones   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── CONTROL DE CALIDAD BIOMOLECULAR ─────────────────────────

CREATE TABLE cc_biomolecular (
    id              SERIAL PRIMARY KEY,
    experimento_id  INTEGER REFERENCES experimentos(id),
    pedido_id       INTEGER REFERENCES pedidos_muestras(id),
    -- datos
    cepa_id         INTEGER REFERENCES cepas(id),
    lote            VARCHAR(100),
    reactor_id      INTEGER REFERENCES reactores(id),
    concentracion   NUMERIC(10,4),
    proteinas_totales NUMERIC(10,4),
    dna_libre       NUMERIC(10,4),
    pureza          NUMERIC(5,3),
    pureza_atb      NUMERIC(5,3),
    hr              NUMERIC(10,4),
    ph              NUMERIC(4,2),
    do_value        NUMERIC(8,4),
    -- metadatos
    fecha           DATE DEFAULT CURRENT_DATE,
    numero_pedido   INTEGER REFERENCES pedidos_muestras(id),
    responsable_id  INTEGER REFERENCES usuarios(id),
    destino_id      INTEGER REFERENCES destinos(id),
    obs1            TEXT,
    obs2            TEXT,
    obs3            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── INÓCULOS ────────────────────────────────────────────────

CREATE TABLE inoculos (
    id              SERIAL PRIMARY KEY,
    tipo            VARCHAR(20) CHECK (tipo IN ('pre_inoculo','inoculo_1','inoculo_2')),
    lote            VARCHAR(100) UNIQUE NOT NULL,
    cepa_id         INTEGER REFERENCES cepas(id),
    medio_id        INTEGER REFERENCES medios_cultivo(id),
    lote_medio      VARCHAR(100),
    lote_preinoculo VARCHAR(100),   -- para inoculo_1
    lote_inoculo    VARCHAR(100),   -- para inoculo_2
    -- medición
    ufc_medio       NUMERIC(20,2),
    recuentos_ufc   NUMERIC[] DEFAULT '{}',
    factor          NUMERIC(6,2) DEFAULT 2.5,
    dilucion        NUMERIC(15,0) DEFAULT 1000000,
    ufc_calculado   NUMERIC(20,2),
    recuentos_conidios NUMERIC[] DEFAULT '{}',
    conidios_calculado NUMERIC(20,2),
    dilucion_conidios  NUMERIC(15,0),
    vol_conidios    NUMERIC(6,3),
    -- pre-inóculo: control de renovación
    fecha_produccion DATE,
    dias_vigencia   INTEGER DEFAULT 25,
    fecha_renovacion DATE GENERATED ALWAYS AS (fecha_produccion + dias_vigencia * INTERVAL '1 day') STORED,
    -- metadatos
    volumen_l       NUMERIC(10,2),
    pureza          VARCHAR(10) CHECK (pureza IN ('SI','NO')),
    registro_pls    VARCHAR(100),
    responsable_id  INTEGER REFERENCES usuarios(id),
    destino_id      INTEGER REFERENCES destinos(id),
    fecha_siembra   DATE,
    estado          VARCHAR(20) DEFAULT 'activo' CHECK (estado IN ('activo','vencido','usado','descartado')),
    notas           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── ENSAYOS ─────────────────────────────────────────────────

CREATE TABLE ensayos (
    id              SERIAL PRIMARY KEY,
    numero          VARCHAR(20) NOT NULL,       -- 1, 2, 3... o PLS-2025-001
    anio            INTEGER NOT NULL,
    titulo          VARCHAR(500) NOT NULL,
    descripcion     TEXT,
    ruta_archivo    VARCHAR(500),               -- ruta red o URL
    estado          VARCHAR(20) DEFAULT 'activo' CHECK (estado IN ('activo','finalizado','pausado','cancelado')),
    responsable_id  INTEGER REFERENCES usuarios(id),
    fecha_inicio    DATE,
    fecha_fin       DATE,
    tags            TEXT[],                     -- [Trichoderma, campo, proteinas…]
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ensayo_resultados (
    id          SERIAL PRIMARY KEY,
    ensayo_id   INTEGER NOT NULL REFERENCES ensayos(id) ON DELETE CASCADE,
    fecha       DATE DEFAULT CURRENT_DATE,
    descripcion TEXT NOT NULL,
    valor       NUMERIC,
    unidad      VARCHAR(50),
    archivo     VARCHAR(500),
    operador_id INTEGER REFERENCES usuarios(id)
);

-- ─── DROGUERO / INVENTARIO ───────────────────────────────────

CREATE TABLE reactivos (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(200) NOT NULL,
    codigo_interno  VARCHAR(50),                -- nombre de flor (Orquídea, Narciso…)
    cas             VARCHAR(20),
    ubicacion       VARCHAR(100),               -- UOVO, GALPON NEGRO, Armario blanco, EN LABORATORIO
    unidad          VARCHAR(10),                -- gr, Kg, mL, L
    stock_minimo    NUMERIC(10,2),
    activo          BOOLEAN DEFAULT TRUE,
    notas           TEXT
);

CREATE TABLE droguero_items (
    id              SERIAL PRIMARY KEY,
    reactivo_id     INTEGER NOT NULL REFERENCES reactivos(id),
    codigo_lote     VARCHAR(100),
    cantidad        NUMERIC(10,3) NOT NULL,
    peso_unidad     NUMERIC(10,3),              -- gr o Kg por unidad
    total_calculado NUMERIC(12,3) GENERATED ALWAYS AS (cantidad * peso_unidad) STORED,
    unidad          VARCHAR(10),
    ubicacion_detalle VARCHAR(100),
    fecha_ingreso   DATE DEFAULT CURRENT_DATE,
    fecha_vencimiento DATE,
    proveedor       VARCHAR(200),
    observaciones   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE droguero_consumos (
    id              SERIAL PRIMARY KEY,
    item_id         INTEGER NOT NULL REFERENCES droguero_items(id),
    cantidad        NUMERIC(10,3) NOT NULL,
    fecha           DATE DEFAULT CURRENT_DATE,
    experimento_id  INTEGER REFERENCES experimentos(id),
    operador_id     INTEGER REFERENCES usuarios(id),
    motivo          TEXT
);

-- ─── VISTA: stock actual ──────────────────────────────────────
CREATE OR REPLACE VIEW v_stock_reactivos AS
SELECT
    r.id,
    r.nombre,
    r.codigo_interno,
    r.ubicacion,
    r.unidad,
    r.stock_minimo,
    COALESCE(SUM(i.total_calculado), 0) -
        COALESCE((SELECT SUM(c.cantidad) FROM droguero_consumos c
                  JOIN droguero_items di ON c.item_id = di.id
                  WHERE di.reactivo_id = r.id), 0) AS stock_actual,
    CASE
        WHEN COALESCE(SUM(i.total_calculado),0) <= r.stock_minimo THEN 'critico'
        WHEN COALESCE(SUM(i.total_calculado),0) <= r.stock_minimo * 2 THEN 'bajo'
        ELSE 'ok'
    END AS estado_stock
FROM reactivos r
LEFT JOIN droguero_items i ON i.reactivo_id = r.id
GROUP BY r.id, r.nombre, r.codigo_interno, r.ubicacion, r.unidad, r.stock_minimo;

-- ─── VISTA: pre-inóculos a vencer ────────────────────────────
CREATE OR REPLACE VIEW v_inoculos_por_vencer AS
SELECT
    i.*,
    (i.fecha_renovacion::date - CURRENT_DATE) AS dias_restantes,
    u.nombre AS responsable_nombre,
    c.nombre AS cepa_nombre
FROM inoculos i
LEFT JOIN usuarios u ON u.id = i.responsable_id
LEFT JOIN cepas c ON c.id = i.cepa_id
WHERE i.estado = 'activo'
  AND i.tipo = 'pre_inoculo'
  AND i.fecha_renovacion IS NOT NULL
ORDER BY dias_restantes;

-- ─── DATOS INICIALES ─────────────────────────────────────────

INSERT INTO cepas (codigo, nombre) VALUES
    ('TH10',  'Trichoderma harzianum 10'),
    ('ARA6',  'Arachidobacter sp. 6'),
    ('T2',    'Trichoderma sp. T2'),
    ('GI9',   'Gluconobacter sp. GI9'),
    ('E109',  'Bradyrhizobium japonicum E109'),
    ('F100',  'Beauveria bassiana F100');

INSERT INTO medios_cultivo (codigo, nombre) VALUES
    ('BRA3',  'BRA 3'),
    ('PDA',   'Potato Dextrose Agar'),
    ('RAMO1', 'RAMO 1'),
    ('RAMO2', 'RAMO 2'),
    ('TTC',   'TTC'),
    ('YMA',   'YMA'),
    ('SP',    'SP');

INSERT INTO reactores (codigo, nombre) VALUES
    ('R1', 'Reactor 1'),('R2', 'Reactor 2'),('R3', 'Reactor 3'),
    ('R4', 'Reactor 4'),('R5', 'Reactor 5'),('R6', 'Reactor 6'),
    ('PP', 'Planta Piloto');

INSERT INTO destinos (nombre) VALUES
    ('Producción'),('Ensayos campo'),('I+D'),('Descarte'),('Otros');

INSERT INTO usuarios (nombre, iniciales, email, rol) VALUES
    ('Dario Vileta',        'DV',  'dario.vileta@protergium.com',    'admin'),
    ('Ainalen Ribas',       'AR',  'ainalen.ribas@protergium.com',   'operador'),
    ('Itati Castillo',      'IC',  'itati.castillo@protergium.com',  'operador'),
    ('Facundo Uviedo',      'FU',  'facundo.uviedo@protergium.com',  'operador'),
    ('Celeste Buschensky',  'CB',  'celeste.buschensky@protergium.com','operador'),
    ('Maria Luz Elisei',    'ML',  'luz.elisei@protergium.com',      'operador'),
    ('Melina Agustinelli',  'MA',  'melina.agustinelli@protergium.com','operador'),
    ('Juan Pablo Quintero', 'JPQ', 'jp.quintero@protergium.com',     'operador'),
    ('Gonzalo Genes',       'GG',  'gonzalo.genes@protergium.com',   'operador'),
    ('Axel Fernandez',      'AF',  'axel.fernandez@protergium.com',  'operador'),
    ('Dino Biciuffa',       'DB',  'dino.biciuffa@protergium.com',   'operador');

INSERT INTO presentaciones (codigo, nombre) VALUES
    ('ERLM_500',   'Erlenmeyer 500 mL'),
    ('ERLM_2000',  'Erlenmeyer 2000 mL'),
    ('BOT_125',    'Botella 125 mL'),
    ('BOT_250',    'Botella 250 mL'),
    ('BOT_500',    'Botella 500 mL'),
    ('BOTELLON_20','Botellón 20 L'),
    ('FALCON_50',  'Falcon 50 mL'),
    ('VASO_100',   'Vaso PP 100 mL'),
    ('VASO_250',   'Vaso PP 250 mL');

-- reactivos del droguero (con sus códigos de flores)
INSERT INTO reactivos (nombre, codigo_interno, ubicacion, unidad) VALUES
    ('Fosfato de potasio monobásico', 'Orquídea',   'UOVO',         'gr'),
    ('Cloruro de sodio',              NULL,           'UOVO',         'gr'),
    ('Fosfato de potasio dibásico',   NULL,           'UOVO',         'gr'),
    ('Sulfato de magnesio',           'Lantana',      'UOVO',         'gr'),
    ('Almidón soluble',               'Flores',       'UOVO',         'gr'),
    ('Fosfato de amonio dibásico',    'Hibisco',      'UOVO',         'gr'),
    ('Sulfato de manganeso',          'Zabila',       'UOVO',         'gr'),
    ('Glucosa',                       'Zinnia',       'UOVO',         'gr'),
    ('Sulfato cúprico',               'Nenufar',      'UOVO',         'gr'),
    ('Sulfato ferroso',               'Liatris',      'UOVO',         'gr'),
    ('Sulfato de zinc',               'Crisantemo',   'UOVO',         'gr'),
    ('Cloruro de manganeso',          'Papiver',      'UOVO',         'gr'),
    ('Cloruro férrico',               'Girasol',      'UOVO',         'gr'),
    ('Extracto de levadura',          'PDA',          'UOVO',         'gr'),
    ('Peptona de carne',              NULL,           'UOVO',         'gr'),
    ('Fosfato de sodio dibásico',     'Vortex azul',  'Armario blanco','gr'),
    ('Nitrato de potasio',            'Vortex rojo',  'Armario blanco','gr'),
    ('Glicerina líquida',             'Vortex violeta','Armario blanco','gr'),
    ('Antiespumante',                 NULL,           'GALPON NEGRO', 'L'),
    -- producción (galpon negro)
    ('Fosfato de potasio monobásico prod', 'Narciso',  'GALPON NEGRO', 'Kg'),
    ('Sulfato de magnesio prod',       'Anemona',      'GALPON NEGRO', 'Kg'),
    ('Fosfato de amonio dibásico prod','Margarita',    'GALPON NEGRO', 'Kg'),
    ('Cloruro ferrico prod',           'Agapanthus',   'GALPON NEGRO', 'gr'),
    ('Antiespumante prod',             'Lavanda',      'GALPON NEGRO', 'Kg');
