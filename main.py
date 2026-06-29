"""
I+D 2026 - Backend API
FastAPI + PostgreSQL
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os, math
from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://id2026:id2026@localhost:5432/id2026")
SECRET_KEY   = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
ALGORITHM    = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI(title="I+D 2026 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ─── DB Dependency ───────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Auth helpers ────────────────────────────────────────────

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(pwd):
    return pwd_context.hash(pwd)

def create_token(data: dict):
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")
    row = db.execute(text("SELECT * FROM usuarios WHERE id=:id AND activo=true"), {"id": user_id}).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return dict(row._mapping)

# ─── Fórmulas de laboratorio ─────────────────────────────────

def calcular_ufc(recuentos: list, factor: float, dilucion: float, volumen: float = 1.0) -> Optional[float]:
    """Promedio de recuentos × factor × dilución / volumen"""
    vals = [r for r in recuentos if r is not None and r > 0]
    if not vals:
        return None
    return round((sum(vals) / len(vals)) * factor * dilucion / volumen, 2)

def calcular_conidios(recuentos: list, factor: float, volumen: float = 1) -> Optional[float]:
    """Promedio × factor (factor ya incluye dilución y constante de cámara)"""
    vals = [r for r in recuentos if r is not None and r > 0]
    if not vals:
        return None
    return round((sum(vals) / len(vals)) * factor, 2)

def formatear_ufc(valor: float) -> str:
    if not valor:
        return "--"
    exp = math.floor(math.log10(valor))
    mantisa = valor / (10 ** exp)
    return f"{mantisa:.2f}×10^{exp}"

# ─── Pydantic Models ─────────────────────────────────────────

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: dict

class ExperimentoCreate(BaseModel):
    nombre: Optional[str] = None
    cepa_id: int
    medio_id: Optional[int] = None
    reactor_id: Optional[int] = None
    volumen_l: Optional[float] = None
    cultivo_objetivo: Optional[str] = None
    producto_final: Optional[str] = None
    temp_objetivo: Optional[float] = 28.0
    ph_objetivo: Optional[float] = 7.2
    lote_medio: Optional[str] = None
    lote_sales: Optional[str] = None
    lote_preinoculo: Optional[str] = None
    lote_inoculo: Optional[str] = None
    responsable_id: Optional[int] = None
    destino_id: Optional[int] = None
    fecha_siembra: Optional[date] = None
    notas: Optional[str] = None

class CCMicroCreate(BaseModel):
    experimento_id: Optional[int] = None
    pedido_id: Optional[int] = None
    cepa_id: Optional[int] = None
    medio_id: Optional[int] = None
    lote_medio: Optional[str] = None
    lote_sales: Optional[str] = None
    lote_preinoculo: Optional[str] = None
    lote_inoculo: Optional[str] = None
    ph: Optional[float] = None
    do_value: Optional[float] = None
    pureza: Optional[str] = None
    recuentos_ufc: List[Optional[float]] = []
    factor_ufc: float = 2.5
    dilucion_ufc: float = 1000000
    recuentos_conidios_1_10: List[Optional[float]] = []
    recuentos_conidios_1_20: List[Optional[float]] = []
    dilucion_conidios: float = 100000000
    vol_conidios: float = 0.1
    responsable_id: Optional[int] = None
    destino_id: Optional[int] = None
    observaciones: Optional[str] = None

class CCBMCreate(BaseModel):
    experimento_id: Optional[int] = None
    pedido_id: Optional[int] = None
    cepa_id: Optional[int] = None
    lote: Optional[str] = None
    reactor_id: Optional[int] = None
    concentracion: Optional[float] = None
    proteinas_totales: Optional[float] = None
    dna_libre: Optional[float] = None
    pureza: Optional[float] = None
    pureza_atb: Optional[float] = None
    hr: Optional[float] = None
    ph: Optional[float] = None
    do_value: Optional[float] = None
    responsable_id: Optional[int] = None
    destino_id: Optional[int] = None
    obs1: Optional[str] = None
    obs2: Optional[str] = None
    obs3: Optional[str] = None

class PedidoCreate(BaseModel):
    fecha_entrega: Optional[date] = None
    solicitante: str
    motivo: Optional[str] = None
    retira: bool = False
    envia: bool = False
    responsable_id: Optional[int] = None
    observaciones: Optional[str] = None
    items: List[dict] = []

class InoculoCreate(BaseModel):
    tipo: str  # pre_inoculo | inoculo_1 | inoculo_2
    cepa_id: int
    medio_id: Optional[int] = None
    lote_medio: Optional[str] = None
    lote_preinoculo: Optional[str] = None
    lote_inoculo: Optional[str] = None
    ufc_medio: Optional[float] = None
    recuentos_ufc: List[Optional[float]] = []
    factor: float = 2.5
    dilucion: float = 1000000
    recuentos_conidios: List[Optional[float]] = []
    dilucion_conidios: Optional[float] = None
    vol_conidios: Optional[float] = None
    volumen_l: Optional[float] = None
    do_value: Optional[float] = None
    pureza: Optional[str] = None
    registro_pls: Optional[str] = None
    responsable_id: Optional[int] = None
    destino_id: Optional[int] = None
    fecha_siembra: Optional[date] = None
    fecha_produccion: Optional[date] = None
    dias_vigencia: int = 25
    notas: Optional[str] = None

# ─── AUTH ────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM usuarios WHERE email=:e AND activo=true"),
        {"e": form.username}
    ).fetchone()
    if not row:
        # fallback: login por iniciales
        row = db.execute(
            text("SELECT * FROM usuarios WHERE iniciales=:i AND activo=true"),
            {"i": form.username.upper()}
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    u = dict(row._mapping)
    # primer login sin contraseña: aceptar cualquier cosa y setear
    if not u.get("password_hash"):
        db.execute(
            text("UPDATE usuarios SET password_hash=:h WHERE id=:id"),
            {"h": hash_password(form.password), "id": u["id"]}
        )
        db.commit()
    elif not verify_password(form.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    token = create_token({"sub": str(u["id"]), "rol": u["rol"]})
    return {"access_token": token, "usuario": {
        "id": u["id"], "nombre": u["nombre"],
        "iniciales": u["iniciales"], "rol": u["rol"],
        "email": u.get("email", "")
    }}

# ─── MAESTROS ────────────────────────────────────────────────

@app.get("/maestros")
def get_maestros(db: Session = Depends(get_db)):
    """Devuelve todos los datos de lookup en una llamada"""
    return {
        "cepas": [dict(r._mapping) for r in db.execute(text("SELECT * FROM cepas WHERE activa=true ORDER BY codigo")).fetchall()],
        "medios": [dict(r._mapping) for r in db.execute(text("SELECT * FROM medios_cultivo WHERE activo=true ORDER BY codigo")).fetchall()],
        "reactores": [dict(r._mapping) for r in db.execute(text("SELECT * FROM reactores WHERE activo=true ORDER BY codigo")).fetchall()],
        "usuarios": [dict(r._mapping) for r in db.execute(text("SELECT id,nombre,iniciales,rol FROM usuarios WHERE activo=true ORDER BY nombre")).fetchall()],
        "destinos": [dict(r._mapping) for r in db.execute(text("SELECT * FROM destinos ORDER BY nombre")).fetchall()],
        "presentaciones": [dict(r._mapping) for r in db.execute(text("SELECT * FROM presentaciones ORDER BY nombre")).fetchall()],
    }

# ─── DASHBOARD ───────────────────────────────────────────────

@app.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    pedidos_activos = db.execute(text(
        "SELECT COUNT(*) FROM pedidos_muestras WHERE estado NOT IN ('entregado','cancelado')"
    )).scalar()
    controles_pendientes = db.execute(text(
        "SELECT COUNT(*) FROM cc_microbiologico WHERE created_at > NOW() - INTERVAL '7 days'"
    )).scalar()
    inoculos_proceso = db.execute(text(
        "SELECT COUNT(*) FROM inoculos WHERE estado='activo'"
    )).scalar()
    inoculos_vencidos = db.execute(text(
        "SELECT COUNT(*) FROM inoculos WHERE estado='vencido' OR (fecha_renovacion IS NOT NULL AND fecha_renovacion::date < CURRENT_DATE)"
    )).scalar()
    ensayos_activos = db.execute(text(
        "SELECT COUNT(*) FROM ensayos WHERE estado='activo'"
    )).scalar()
    ensayos_en_proceso = db.execute(text(
        "SELECT COUNT(*) FROM ensayos WHERE estado='en_proceso'"
    )).scalar()
    ensayos_finalizados = db.execute(text(
        "SELECT COUNT(*) FROM ensayos WHERE estado='finalizado'"
    )).scalar()
    inoculos_por_vencer = db.execute(text(
        "SELECT * FROM v_inoculos_por_vencer WHERE dias_restantes <= 7 ORDER BY dias_restantes"
    )).fetchall()
    stock_critico = db.execute(text(
        "SELECT * FROM v_stock_reactivos WHERE estado_stock IN ('critico','bajo') ORDER BY estado_stock"
    )).fetchall()
    ultimos_pedidos = db.execute(text(
        """SELECT p.*, u.nombre as responsable_nombre
           FROM pedidos_muestras p
           LEFT JOIN usuarios u ON u.id = p.responsable_id
           ORDER BY p.created_at DESC LIMIT 10"""
    )).fetchall()
    return {
        "kpis": {
            "pedidos_activos": pedidos_activos,
            "controles_pendientes": controles_pendientes,
            "inoculos_proceso": inoculos_proceso,
            "inoculos_vencidos": inoculos_vencidos,
            "ensayos_activos": ensayos_activos,
            "ensayos_en_proceso": ensayos_en_proceso,
            "ensayos_finalizados": ensayos_finalizados,
        },
        "alertas": {
            "inoculos_por_vencer": [dict(r._mapping) for r in inoculos_por_vencer],
            "stock_critico": [dict(r._mapping) for r in stock_critico],
        },
        "ultimos_pedidos": [dict(r._mapping) for r in ultimos_pedidos],
    }

# ─── EXPERIMENTOS / BATCH ────────────────────────────────────

def generar_lote(cepa_codigo: str, medio_codigo: str, db: Session) -> str:
    hoy = date.today().strftime("%Y%m%d")
    count = db.execute(text(
        "SELECT COUNT(*) FROM experimentos WHERE DATE(created_at)=CURRENT_DATE"
    )).scalar()
    return f"{cepa_codigo}-{medio_codigo}-{hoy}-{(count+1):03d}"

@app.post("/experimentos", status_code=201)
def crear_experimento(data: ExperimentoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cepa = db.execute(text("SELECT codigo FROM cepas WHERE id=:id"), {"id": data.cepa_id}).fetchone()
    medio = db.execute(text("SELECT codigo FROM medios_cultivo WHERE id=:id"), {"id": data.medio_id}).fetchone() if data.medio_id else None
    lote = generar_lote(cepa.codigo if cepa else "XX", medio.codigo if medio else "XX", db)
    row = db.execute(text("""
        INSERT INTO experimentos (lote,nombre,cepa_id,medio_id,reactor_id,volumen_l,
            cultivo_objetivo,producto_final,temp_objetivo,ph_objetivo,
            lote_medio,lote_sales,lote_preinoculo,lote_inoculo,
            responsable_id,destino_id,fecha_siembra,notas)
        VALUES (:lote,:nombre,:cepa_id,:medio_id,:reactor_id,:volumen_l,
            :cultivo_objetivo,:producto_final,:temp_objetivo,:ph_objetivo,
            :lote_medio,:lote_sales,:lote_preinoculo,:lote_inoculo,
            :responsable_id,:destino_id,:fecha_siembra,:notas)
        RETURNING id, lote
    """), {**data.dict(), "lote": lote}).fetchone()
    db.commit()
    return {"id": row.id, "lote": row.lote}

@app.get("/experimentos")
def listar_experimentos(
    estado: Optional[str] = None,
    cepa_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    filters = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if estado:
        filters += " AND e.estado=:estado"; params["estado"] = estado
    if cepa_id:
        filters += " AND e.cepa_id=:cepa_id"; params["cepa_id"] = cepa_id
    rows = db.execute(text(f"""
        SELECT e.*, c.nombre as cepa_nombre, c.codigo as cepa_codigo,
               m.nombre as medio_nombre, r.nombre as reactor_nombre,
               u.nombre as responsable_nombre, d.nombre as destino_nombre
        FROM experimentos e
        LEFT JOIN cepas c ON c.id = e.cepa_id
        LEFT JOIN medios_cultivo m ON m.id = e.medio_id
        LEFT JOIN reactores r ON r.id = e.reactor_id
        LEFT JOIN usuarios u ON u.id = e.responsable_id
        LEFT JOIN destinos d ON d.id = e.destino_id
        {filters}
        ORDER BY e.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()
    total = db.execute(text(f"SELECT COUNT(*) FROM experimentos e {filters}"), params).scalar()
    return {"items": [dict(r._mapping) for r in rows], "total": total}

@app.get("/experimentos/{id}")
def get_experimento(id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT e.*, c.nombre as cepa_nombre, m.nombre as medio_nombre,
               r.nombre as reactor_nombre, u.nombre as responsable_nombre, d.nombre as destino_nombre
        FROM experimentos e
        LEFT JOIN cepas c ON c.id = e.cepa_id
        LEFT JOIN medios_cultivo m ON m.id = e.medio_id
        LEFT JOIN reactores r ON r.id = e.reactor_id
        LEFT JOIN usuarios u ON u.id = e.responsable_id
        LEFT JOIN destinos d ON d.id = e.destino_id
        WHERE e.id=:id
    """), {"id": id}).fetchone()
    if not row: raise HTTPException(404, "No encontrado")
    exp = dict(row._mapping)
    exp["mediciones"] = [dict(r._mapping) for r in db.execute(text(
        "SELECT * FROM experimento_mediciones WHERE experimento_id=:id ORDER BY fecha_hora DESC"
    ), {"id": id}).fetchall()]
    exp["cc_micro"] = [dict(r._mapping) for r in db.execute(text(
        "SELECT * FROM cc_microbiologico WHERE experimento_id=:id ORDER BY created_at DESC"
    ), {"id": id}).fetchall()]
    return exp

@app.patch("/experimentos/{id}/estado")
def cambiar_estado(id: int, estado: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user["rol"] not in ("admin","operador"):
        raise HTTPException(403)
    db.execute(text("UPDATE experimentos SET estado=:e, updated_at=NOW() WHERE id=:id"), {"e": estado, "id": id})
    db.commit()
    return {"ok": True}

# ─── CC MICROBIOLÓGICO ───────────────────────────────────────

@app.post("/cc/micro", status_code=201)
def crear_cc_micro(data: CCMicroCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ufc = calcular_ufc(data.recuentos_ufc, data.factor_ufc, data.dilucion_ufc)
    coni_10 = calcular_conidios(data.recuentos_conidios_1_10, data.dilucion_conidios, data.vol_conidios)
    coni_20 = calcular_conidios(data.recuentos_conidios_1_20, data.dilucion_conidios, data.vol_conidios * 2)
    row = db.execute(text("""
        INSERT INTO cc_microbiologico (
            experimento_id,pedido_id,cepa_id,medio_id,lote_medio,lote_sales,
            lote_preinoculo,lote_inoculo,ph,do_value,pureza,
            recuentos_ufc,factor_ufc,dilucion_ufc,ufc_calculado,
            recuentos_conidios_1_10,recuentos_conidios_1_20,
            conidios_1_10_calculado,conidios_1_20_calculado,
            dilucion_conidios,vol_conidios,
            responsable_id,destino_id,observaciones
        ) VALUES (
            :experimento_id,:pedido_id,:cepa_id,:medio_id,:lote_medio,:lote_sales,
            :lote_preinoculo,:lote_inoculo,:ph,:do_value,:pureza,
            :recuentos_ufc,:factor_ufc,:dilucion_ufc,:ufc_calculado,
            :recuentos_conidios_1_10,:recuentos_conidios_1_20,
            :conidios_1_10,:conidios_1_20,
            :dilucion_conidios,:vol_conidios,
            :responsable_id,:destino_id,:observaciones
        ) RETURNING id
    """), {
        **data.dict(),
        "ufc_calculado": ufc,
        "conidios_1_10": coni_10,
        "conidios_1_20": coni_20,
        "recuentos_ufc": data.recuentos_ufc,
        "recuentos_conidios_1_10": data.recuentos_conidios_1_10,
        "recuentos_conidios_1_20": data.recuentos_conidios_1_20,
    }).fetchone()
    db.commit()
    return {
        "id": row.id,
        "ufc_calculado": ufc,
        "ufc_formateado": formatear_ufc(ufc),
        "conidios_1_10": coni_10,
        "conidios_1_20": coni_20,
    }

@app.get("/cc/micro")
def listar_cc_micro(
    experimento_id: Optional[int] = None,
    cepa_id: Optional[int] = None,
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db), _=Depends(get_current_user)
):
    filters = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if experimento_id: filters += " AND cc.experimento_id=:eid"; params["eid"] = experimento_id
    if cepa_id: filters += " AND cc.cepa_id=:cid"; params["cid"] = cepa_id
    rows = db.execute(text(f"""
        SELECT cc.*, c.nombre as cepa_nombre, u.nombre as responsable_nombre,
               d.nombre as destino_nombre
        FROM cc_microbiologico cc
        LEFT JOIN cepas c ON c.id = cc.cepa_id
        LEFT JOIN usuarios u ON u.id = cc.responsable_id
        LEFT JOIN destinos d ON d.id = cc.destino_id
        {filters}
        ORDER BY cc.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()
    total = db.execute(text(f"SELECT COUNT(*) FROM cc_microbiologico cc {filters}"), params).scalar()
    return {"items": [dict(r._mapping) for r in rows], "total": total}

# ─── CC BIOMOLECULAR ─────────────────────────────────────────

@app.post("/cc/biomolecular", status_code=201)
def crear_cc_bm(data: CCBMCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO cc_biomolecular (
            experimento_id,pedido_id,cepa_id,lote,reactor_id,concentracion,
            proteinas_totales,dna_libre,pureza,pureza_atb,hr,ph,do_value,
            responsable_id,destino_id,obs1,obs2,obs3
        ) VALUES (
            :experimento_id,:pedido_id,:cepa_id,:lote,:reactor_id,:concentracion,
            :proteinas_totales,:dna_libre,:pureza,:pureza_atb,:hr,:ph,:do_value,
            :responsable_id,:destino_id,:obs1,:obs2,:obs3
        ) RETURNING id
    """), data.dict()).fetchone()
    db.commit()
    return {"id": row.id}

@app.get("/cc/biomolecular")
def listar_cc_bm(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT cb.*, c.nombre as cepa_nombre, u.nombre as responsable_nombre
        FROM cc_biomolecular cb
        LEFT JOIN cepas c ON c.id = cb.cepa_id
        LEFT JOIN usuarios u ON u.id = cb.responsable_id
        ORDER BY cb.created_at DESC LIMIT :l OFFSET :o
    """), {"l": limit, "o": offset}).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

# ─── PEDIDOS DE MUESTRAS ─────────────────────────────────────

@app.post("/pedidos", status_code=201)
def crear_pedido(data: PedidoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    # siguiente número correlativo
    ultimo = db.execute(text("SELECT COALESCE(MAX(numero),184) FROM pedidos_muestras")).scalar()
    numero = ultimo + 1
    row = db.execute(text("""
        INSERT INTO pedidos_muestras (numero,fecha_entrega,solicitante,motivo,retira,envia,responsable_id,observaciones)
        VALUES (:numero,:fecha_entrega,:solicitante,:motivo,:retira,:envia,:responsable_id,:observaciones)
        RETURNING id, numero
    """), {**data.dict(exclude={"items"}), "numero": numero}).fetchone()
    pid = row.id
    for item in data.items:
        db.execute(text("""
            INSERT INTO pedido_muestras_items (pedido_id,rotulo,volumen_l,presentacion_id,observaciones)
            VALUES (:pedido_id,:rotulo,:volumen_l,:presentacion_id,:observaciones)
        """), {
            "pedido_id": pid,
            "rotulo": item.get("rotulo"),
            "volumen_l": item.get("volumen_l"),
            "presentacion_id": item.get("presentacion_id"),
            "observaciones": item.get("observaciones"),
        })
    db.commit()
    return {"id": pid, "numero": row.numero}

@app.get("/pedidos")
def listar_pedidos(estado: Optional[str] = None, limit: int = 50, offset: int = 0,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    filters = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if estado: filters += " AND p.estado=:estado"; params["estado"] = estado
    rows = db.execute(text(f"""
        SELECT p.*, u.nombre as responsable_nombre
        FROM pedidos_muestras p
        LEFT JOIN usuarios u ON u.id = p.responsable_id
        {filters}
        ORDER BY p.numero DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()
    total = db.execute(text(f"SELECT COUNT(*) FROM pedidos_muestras p {filters}"), params).scalar()
    return {"items": [dict(r._mapping) for r in rows], "total": total}

@app.get("/pedidos/{id}")
def get_pedido(id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT p.*, u.nombre as responsable_nombre
        FROM pedidos_muestras p
        LEFT JOIN usuarios u ON u.id = p.responsable_id
        WHERE p.id=:id
    """), {"id": id}).fetchone()
    if not row: raise HTTPException(404)
    p = dict(row._mapping)
    p["items"] = [dict(r._mapping) for r in db.execute(text(
        "SELECT * FROM pedido_muestras_items WHERE pedido_id=:id"
    ), {"id": id}).fetchall()]
    return p

@app.patch("/pedidos/{id}/estado")
def actualizar_estado_pedido(id: int, estado: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    db.execute(text("UPDATE pedidos_muestras SET estado=:e, updated_at=NOW() WHERE id=:id"), {"e": estado, "id": id})
    db.commit()
    return {"ok": True}

# ─── INÓCULOS ────────────────────────────────────────────────

@app.post("/inoculos", status_code=201)
def crear_inoculo(data: InoculoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ufc = calcular_ufc(data.recuentos_ufc, data.factor, data.dilucion)
    conidios = calcular_conidios(data.recuentos_conidios, data.dilucion_conidios or 1e8, data.vol_conidios or 0.1) if data.recuentos_conidios else None
    hoy = date.today().strftime("%Y%m%d")
    count = db.execute(text("SELECT COUNT(*) FROM inoculos WHERE DATE(created_at)=CURRENT_DATE")).scalar()
    lote = f"IN-{data.tipo.upper()[:4]}-{hoy}-{(count+1):03d}"
    row = db.execute(text("""
        INSERT INTO inoculos (tipo,lote,cepa_id,medio_id,lote_medio,lote_preinoculo,lote_inoculo,
            ufc_medio,recuentos_ufc,factor,dilucion,ufc_calculado,
            recuentos_conidios,conidios_calculado,dilucion_conidios,vol_conidios,
            volumen_l,do_value,pureza,registro_pls,responsable_id,destino_id,
            fecha_siembra,fecha_produccion,dias_vigencia,notas)
        VALUES (:tipo,:lote,:cepa_id,:medio_id,:lote_medio,:lote_preinoculo,:lote_inoculo,
            :ufc_medio,:recuentos_ufc,:factor,:dilucion,:ufc_calculado,
            :recuentos_conidios,:conidios_calculado,:dilucion_conidios,:vol_conidios,
            :volumen_l,:do_value,:pureza,:registro_pls,:responsable_id,:destino_id,
            :fecha_siembra,:fecha_produccion,:dias_vigencia,:notas)
        RETURNING id, lote
    """), {
        **data.dict(),
        "lote": lote,
        "ufc_calculado": ufc,
        "conidios_calculado": conidios,
        "recuentos_ufc": data.recuentos_ufc,
        "recuentos_conidios": data.recuentos_conidios,
    }).fetchone()
    db.commit()
    return {"id": row.id, "lote": row.lote, "ufc_calculado": ufc}

@app.get("/inoculos")
def listar_inoculos(tipo: Optional[str] = None, estado: Optional[str] = None,
                    limit: int = 50, offset: int = 0,
                    db: Session = Depends(get_db), _=Depends(get_current_user)):
    filters = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if tipo: filters += " AND i.tipo=:tipo"; params["tipo"] = tipo
    if estado: filters += " AND i.estado=:estado"; params["estado"] = estado
    rows = db.execute(text(f"""
        SELECT i.*, c.nombre as cepa_nombre, u.nombre as responsable_nombre,
               (i.fecha_renovacion::date - CURRENT_DATE) as dias_restantes
        FROM inoculos i
        LEFT JOIN cepas c ON c.id = i.cepa_id
        LEFT JOIN usuarios u ON u.id = i.responsable_id
        {filters}
        ORDER BY i.created_at DESC LIMIT :limit OFFSET :offset
    """), params).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

# ─── ENSAYOS R&D ─────────────────────────────────────────────

@app.get("/ensayos")
def listar_ensayos(estado: Optional[str] = None, anio: Optional[int] = None,
                   limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_user)):
    filters = "WHERE 1=1"
    params: dict = {"limit": limit}
    if estado: filters += " AND e.estado=:estado"; params["estado"] = estado
    if anio: filters += " AND e.anio=:anio"; params["anio"] = anio
    rows = db.execute(text(f"""
        SELECT e.*,
               ul.nombre as lider_nombre,
               ur.nombre as responsable_nombre,
               c.nombre as cepa_nombre, c.codigo as cepa_codigo,
               m.nombre as medio_nombre,
               r.nombre as reactor_nombre,
               d.nombre as destino_nombre
        FROM ensayos e
        LEFT JOIN usuarios ul ON ul.id = e.lider_id
        LEFT JOIN usuarios ur ON ur.id = e.responsable_id
        LEFT JOIN cepas c ON c.id = e.cepa_id
        LEFT JOIN medios_cultivo m ON m.id = e.medio_id
        LEFT JOIN reactores r ON r.id = e.reactor_id
        LEFT JOIN destinos d ON d.id = e.destino_id
        {filters}
        ORDER BY e.anio DESC, e.numero DESC LIMIT :limit
    """), params).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

@app.post("/ensayos", status_code=201)
def crear_ensayo(data: dict, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.execute(text("""
        INSERT INTO ensayos (numero,anio,titulo,descripcion,ruta_archivo,estado,fecha_inicio,
                            lider_id,responsable_id,cepa_id,medio_id,reactor_id,
                            volumen_l,cultivo_objetivo,producto_final,temp_objetivo,ph_objetivo,
                            lote_medio,lote_sales,lote_preinoculo,lote_inoculo,
                            destino_id,fecha_siembra,notas)
        VALUES (:numero,:anio,:titulo,:descripcion,:ruta_archivo,:estado,:fecha_inicio,
                :lider_id,:responsable_id,:cepa_id,:medio_id,:reactor_id,
                :volumen_l,:cultivo_objetivo,:producto_final,:temp_objetivo,:ph_objetivo,
                :lote_medio,:lote_sales,:lote_preinoculo,:lote_inoculo,
                :destino_id,:fecha_siembra,:notas)
        RETURNING id
    """), {
        "numero": data.get("numero"),
        "anio": data.get("anio", date.today().year),
        "titulo": data.get("titulo"),
        "descripcion": data.get("descripcion"),
        "ruta_archivo": data.get("ruta_archivo"),
        "estado": data.get("estado", "activo"),
        "fecha_inicio": data.get("fecha_inicio"),
        "lider_id": data.get("lider_id"),
        "responsable_id": data.get("responsable_id"),
        "cepa_id": data.get("cepa_id"),
        "medio_id": data.get("medio_id"),
        "reactor_id": data.get("reactor_id"),
        "volumen_l": data.get("volumen_l"),
        "cultivo_objetivo": data.get("cultivo_objetivo"),
        "producto_final": data.get("producto_final"),
        "temp_objetivo": data.get("temp_objetivo"),
        "ph_objetivo": data.get("ph_objetivo"),
        "lote_medio": data.get("lote_medio"),
        "lote_sales": data.get("lote_sales"),
        "lote_preinoculo": data.get("lote_preinoculo"),
        "lote_inoculo": data.get("lote_inoculo"),
        "destino_id": data.get("destino_id"),
        "fecha_siembra": data.get("fecha_siembra"),
        "notas": data.get("notas"),
    }).fetchone()
    db.commit()
    return {"id": row.id}

@app.patch("/ensayos/{id}/estado", status_code=200)
def cambiar_estado_ensayo(id: int, estado: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    db.execute(text("UPDATE ensayos SET estado=:e WHERE id=:id"), {"e": estado, "id": id})
    db.commit()
    return {"ok": True}

# ─── DROGUERO ────────────────────────────────────────────────

@app.get("/droguero/stock")
def get_stock(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("SELECT * FROM v_stock_reactivos ORDER BY estado_stock, nombre")).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

@app.get("/droguero/reactivos")
def listar_reactivos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.execute(text("SELECT * FROM reactivos WHERE activo=true ORDER BY nombre")).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

@app.post("/droguero/consumo")
def registrar_consumo(data: dict, db: Session = Depends(get_db), _=Depends(get_current_user)):
    db.execute(text("""
        INSERT INTO droguero_consumos (item_id,cantidad,experimento_id,operador_id,motivo)
        VALUES (:item_id,:cantidad,:experimento_id,:operador_id,:motivo)
    """), data)
    db.commit()
    return {"ok": True}

# ─── MEDIOS DE CULTIVO ───────────────────────────────────────

class MedioPedidoCreate(BaseModel):
    fecha_solicitada: Optional[date] = None
    fecha_requerida: Optional[date] = None
    medio: str
    volumen_l: Optional[float] = None
    presentacion: Optional[str] = None
    num_unidades: Optional[int] = None
    solicitante_id: Optional[int] = None
    responsable_id: Optional[int] = None
    observaciones: Optional[str] = None

@app.post("/medios/pedidos", status_code=201)
def crear_medio_pedido(data: MedioPedidoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    ultimo = db.execute(text("SELECT COALESCE(MAX(numero),0) FROM medios_pedidos")).scalar()
    numero = ultimo + 1
    row = db.execute(text("""
        INSERT INTO medios_pedidos (numero,fecha_solicitada,fecha_requerida,medio,volumen_l,presentacion,num_unidades,
            solicitante_id,responsable_id,observaciones)
        VALUES (:numero,:fecha_solicitada,:fecha_requerida,:medio,:volumen_l,:presentacion,:num_unidades,
            :solicitante_id,:responsable_id,:observaciones)
        RETURNING id, numero
    """), {**data.dict(), "numero": numero}).fetchone()
    db.commit()
    return {"id": row.id, "numero": row.numero}

@app.get("/medios/pedidos")
def listar_medios_pedidos(estado: Optional[str] = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    filters = "WHERE 1=1"
    params: dict = {}
    if estado: filters += " AND mp.estado=:estado"; params["estado"] = estado
    rows = db.execute(text(f"""
        SELECT mp.*, us.nombre as solicitante_nombre, ur.nombre as responsable_nombre
        FROM medios_pedidos mp
        LEFT JOIN usuarios us ON us.id = mp.solicitante_id
        LEFT JOIN usuarios ur ON ur.id = mp.responsable_id
        {filters}
        ORDER BY mp.numero DESC
        LIMIT 100
    """), params).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}

@app.patch("/medios/pedidos/{id}/estado")
def actualizar_estado_medio_pedido(id: int, estado: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    db.execute(text("UPDATE medios_pedidos SET estado=:e, updated_at=NOW() WHERE id=:id"), {"e": estado, "id": id})
    db.commit()
    return {"ok": True}

# ─── ELIMINACIÓN (solo Dario Vileta) ─────────────────────────

ADMIN_EMAIL = "dario.vileta@protergium.com"

def _check_admin(user):
    if user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Solo Dario Vileta puede eliminar registros")

@app.delete("/pedidos/{id}", status_code=204)
def eliminar_pedido(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM pedidos_muestras WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/experimentos/{id}", status_code=204)
def eliminar_experimento(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM experimentos WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/cc/micro/{id}", status_code=204)
def eliminar_cc_micro(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM cc_microbiologico WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/cc/biomolecular/{id}", status_code=204)
def eliminar_cc_bm(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM cc_biomolecular WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/medios/pedidos/{id}", status_code=204)
def eliminar_medio_pedido(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM medios_pedidos WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/ensayos/{id}", status_code=204)
def eliminar_ensayo(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM ensayos WHERE id=:id"), {"id": id})
    db.commit()

@app.delete("/inoculos/{id}", status_code=204)
def eliminar_inoculo(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _check_admin(user)
    db.execute(text("DELETE FROM inoculos WHERE id=:id"), {"id": id})
    db.commit()

# ─── HEALTH ──────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
