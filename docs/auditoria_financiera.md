# Auditoría técnica del Informe 01

- Fecha: 2026-11-19
- Alcance: `informes/2026-11-19_informe-01_candidatos.md`
- Modo: solo lectura. No se modificó Effi, no se autorizaron operaciones comerciales y no se gastó presupuesto publicitario.

## Resumen ejecutivo

| Área | Veredicto | Impacto en el Informe 01 |
|---|---|---|
| Effi (MCP) | Funciona en lectura, pero **el catálogo de proveedores no está en el alcance del MCP**. Inventario propio: 2 artículos, stock 0 | No hay costos reales: todo el modelo se apoya en el techo PVP/3 |
| Meta Ad Library | **Sin acceso efectivo.** La API pide un token; la web responde con un reto anti-bot (403) | La evidencia en Meta del informe está correctamente marcada PENDIENTE |
| TikTok Creative Center | **Sin acceso efectivo.** El HTML inicial no trae datos; el navegador automatizado recibe 403 | La evidencia en TikTok está correctamente marcada PENDIENTE |
| Finanzas | **Fórmulas correctas y verificadas** (6/6 pruebas). Hay **omisiones**: IVA del 19 % sobre la pauta, GMF y tasas de devolución sin datos | Los CPA máximos están **sobreestimados alrededor de un 16 %** (falta el IVA) |
| Fuentes alternativas | Solo funciona `WebSearch` (fuentes secundarias). El resto requiere abrir la red, tener una cuenta o hacerlo a mano | Los candidatos son hipótesis, no productos validados |

---

## 1. Effi ERP (MCP "POBA")

**Problema encontrado.** El MCP solo expone los datos de la empresa conectada (Poba shop, id 57517): sus artículos, terceros y transacciones. **No hay ningún recurso para el marketplace o catálogo de proveedores dropshipping.** Además, el inventario propio está prácticamente vacío.

**Evidencia técnica.**
- `empresa_contexto`: empresa Poba shop, usuario con "Perfil de usuario principal", 95 recursos y 7 bloques de indicadores (alertas, wallets, inventario, logística, clientes, comercial, chat). **No hay bloque `ventas`.**
- `recursos_disponibles(buscar="drop")` devuelve `{"recursos": []}`: no existe ningún recurso de dropshipping o marketplace.
- `consultar_recurso(articulo)` devuelve **2 artículos**:
  - id 5 "BOLSO KP ESSENCE": p_costo 0, precio 0, stock 0.
  - id 1 "Flete": servicio sin stock.
- `articulo` con `dropshipping_distribuidor=1` devuelve solo "Flete", así que no hay ningún producto vinculado a un proveedor dropshipping.
- Los campos de costo (`p_costo*`) y stock (`stock_empresa`) **sí aparecen** en la respuesta, lo que indica que el perfil **tiene** los permisos de costos (función 155) y de stock (función 156).
- `indicadores(inventario)`: valor $0. `ultima_carga` es 2026-11-02 (unos 17 días de retraso) y `permisos.ventas: false`, de modo que las listas `mas_vendidos` y `menor_rotacion` vienen con `total: null`.
- `indicadores(logistica, 2026-01-01 → 2026-11-19)`: **0 guías, 0 entregas, 0 devoluciones.** No hay histórico propio de devolución.
- `bodega`: 1 sola bodega ("Principal").
- `proveedor`: 110 terceros. La muestra revisada son en su mayoría entidades parafiscales (SENA, ICBF, cajas de compensación) y 1 comercial (HANEY S.A.S.).

**Clasificación de la limitación.**

| Posible causa | ¿Aplica? | Evidencia |
|---|---|---|
| Permisos del usuario sobre costos y stock | No | Los campos de costo y stock se devuelven |
| Permiso de reportes de ventas | **Sí (parcial)** | `permisos.ventas: false`; no hay bloque `ventas` |
| **Alcance del MCP** | **Sí (principal)** | No existe ningún recurso de catálogo de proveedores; el MCP es por empresa y usuario |
| Datos de la empresa | **Sí** | Inventario y logística vacíos |

**Qué funciona.** La lectura de artículos con costo y stock por bodega, terceros, guías, devoluciones, cobertura de transportadoras, indicadores de logística e inventario, y la documentación de cada recurso.

**Qué no funciona.** Consultar el catálogo de proveedores de terceros, leer un histórico propio de devoluciones o fletes (no existe) y ver el ranking de ventas (sin permiso).

**Solución propuesta.**
1. El usuario vincula manualmente en Effi (desde la web) los productos candidatos del catálogo de proveedores.
2. Después, la lectura por MCP de `articulo` con `dropshipping_distribuidor=1` devuelve `p_costo` y `stock_bodegas` reales.
3. Opcional: dar al perfil el permiso de reportes de ventas para activar `mas_vendidos` cuando haya ventas.
4. Usar `cobertura_transportadora_efficommerce` para validar la cobertura en las ciudades objetivo antes de pautar.

**Costos o limitaciones.** El trabajo de vinculación es manual y lo hace el usuario. Las herramientas de escritura del MCP (`crear_recurso`, `modificar_recurso`, `anular_recurso`) existen, pero **no se usarán** sin autorización explícita.

---

## 2. Meta Ad Library

**Problema encontrado.** Hoy no hay ninguna vía oficial y automatizable para contar anuncios comerciales activos en Colombia desde este entorno.

**Evidencia técnica.**
- Red: el entorno "POBA- product scout" permite `www.facebook.com` y `graph.facebook.com`. Con `curl` por el proxy, la conexión se establece.
- API oficial: `GET graph.facebook.com/v21.0/ads_archive?...ad_reached_countries=['CO']` sin token devuelve `{"error":{"type":"OAuthException","code":1}}`. **Requiere un token de acceso.**
- Web: `GET www.facebook.com/ads/library/?country=CO&q=masajeador` devuelve **HTTP 403** con la página "Ad Library" y un script `executeChallenge()` (`/__rd_verify_...`), que es un reto anti-bot. **No se intentó evadirlo.**
- `WebFetch` falla con `ENOTFOUND` porque no usa el proxy de la sesión. El primer `curl` del informe 01 lo bloqueó el clasificador de permisos.

**Qué se puede consultar oficialmente para Colombia** (según la documentación pública de Meta; conviene confirmarlo al crear la app):

| Vía | Requisitos | Datos para Colombia |
|---|---|---|
| API `ads_archive` | App de Meta para desarrolladores, verificación de identidad y token de usuario | **Solo anuncios de temas sociales, elecciones o política.** Los anuncios comerciales se exponen por API solo cuando se entregan en la UE/EEE (DSA). **No sirve para productos en Colombia** |
| Web de Ad Library (humano en navegador) | Ninguno | Todos los anuncios activos: anunciante, creativo, fecha "Comenzó a circular", plataformas y número de versiones. **Sin gasto ni alcance** para anuncios comerciales |

**Qué funciona.** La conexión de red hacia los hosts de Meta.

**Qué no funciona.** La API para anuncios comerciales en Colombia (por su alcance, no por la red) y la web automatizada (reto anti-bot).

**Solución propuesta.**
1. **Verificación manual guiada:** genero los enlaces de búsqueda (país CO, activos, palabra clave) y una plantilla CSV. El usuario anota anunciante, fecha de inicio y precio visto.
2. Alternativa: usar el navegador del propio usuario con su sesión, mediante la extensión Claude in Chrome. Es acceso legítimo como usuario y nadie automatiza la evasión.
3. Proveedor de datos de terceros con API, de pago y con licencia.

**Costos o limitaciones.** La vía manual cuesta unos 5 minutos por producto. Los proveedores de pago cuestan dinero y hay que revisar sus términos. La fecha de inicio es solo un indicio de validación: no prueba rentabilidad.

---

## 3. TikTok Creative Center

**Problema encontrado.** Los datos de Top Ads y de tendencias no vienen en el HTML inicial. Se cargan desde el navegador contra una API interna firmada, y el navegador automatizado recibe 403.

**Evidencia técnica.**
- `curl` a `ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?region=CO` devuelve HTTP 200, con el título "Top Ads: high-performing auction ads". Pero `__NEXT_DATA__.props.pageProps.data` es `{"materials": []}`: **0 anuncios en el HTML inicial.**
- Chromium headless (Playwright) a la misma URL devuelve **HTTP 403**, con el cuerpo vacío.
- No se falsificaron firmas, cabeceras ni user-agent, ni se usó una API interna.

**Secciones de Creative Center** (según su documentación pública) y su estado de acceso:

| Sección | Datos que ofrece | Acceso desde aquí |
|---|---|---|
| Top Ads | Creativos, industria, objetivo, likes, CTR relativo | No (403 o vacío) |
| Top Products | Categoría, popularidad, CTR, CVR, impresiones | No. Algunas fuentes dicen que requiere iniciar sesión |
| Keyword Insights | Palabras clave con volumen relativo | No |
| Trend Discovery (hashtags, canciones, creadores, videos) | Tendencia por región | No |

La disponibilidad de **Colombia** en cada filtro de región **no se pudo verificar** desde aquí.

**Qué funciona.** La conexión de red y la estructura de la página.

**Qué no funciona.** Extraer cualquier métrica.

**Solución propuesta.**
1. Revisión manual del usuario en Creative Center (región CO, últimos 30 días), con una plantilla de captura.
2. Claude in Chrome en el navegador del usuario.
3. API oficial de investigación o Commercial Content API de TikTok: requiere solicitar acceso y su cobertura de anuncios está orientada a Europa, así que es poco útil para Colombia.

**Costos o limitaciones.** Iguales a los de Meta. Las métricas de Creative Center son relativas y no dan ventas.

---

## 4. Finanzas: revisión de fórmulas

**Fórmula auditada** (por **pedido generado**; r = tasa de devolución o rechazo):

| Componente | Entregado (prob. 1−r) | Rechazado (prob. r) |
|---|---|---|
| Recaudo (PVP) | +P | 0 |
| Comisión COD | −k·P | 0 (no hay recaudo) |
| Costo del producto | −C | 0 (supuesto: la mercancía vuelve al proveedor) |
| Flete de ida | −Fi | −Fi |
| Flete de retorno | 0 | −Fr |
| Pauta (CPA) | −A·(1+IVA) | −A·(1+IVA) |

- U(A) = (1−r)·(P·(1−k) − C − Fi) − r·(Fi + Fr) − A·(1+IVA)
- **CPA máx** = [(1−r)·(P·(1−k) − C − Fi) − r·(Fi + Fr)] / (1+IVA)

Supuestos del informe 01: Fi = Fr = $20.000; k = 3 %; C = P/3; IVA de la pauta = 0; CPA objetivo = 60 % del CPA máximo.

**Prueba matemática** (`scripts/test_modelo_financiero.py`, con aritmética exacta usando `Fraction`). Resultado: **6/6 OK**.
1. **Punto de equilibrio exacto:** U(CPA máx) = 0 para los 5 productos, con r ∈ {10, 15, 20, 30 %} y con y sin IVA. Además, el CPA máximo decrece de forma estricta al subir r.
2. **Derivación independiente:** el valor esperado enumerado por ramas (entregado o rechazado, probabilidades que suman 1) coincide **exactamente** con la fórmula cerrada.
3. **Monte Carlo:** 400.000 pedidos simulados (semilla fija) convergen al valor exacto con un error menor de $300, unos 5 errores estándar.
4. **Regresión:** **todos** los CPA máximos y márgenes publicados en el informe 01 coinciden con el modelo (±1 COP por redondeo).
5. **Umbral:** el PVP mínimo para un CPA máximo de $20.000 (r = 15 %, sin IVA) es **$79.458**, lo que confirma la frase "PVP < ~$80k → CPA máx < $20k".
6. **Desglose:** 119.900 − 3.597 − 39.967 − 20.000 = 56.336 ✔.

**Problemas encontrados en el informe 01.**

| # | Problema | Severidad | Evidencia / corrección |
|---|---|---|---|
| F1 | **Falta el IVA del 19 % sobre la pauta digital.** Meta y TikTok facturan IVA a anunciantes colombianos por servicios digitales del exterior (confirmar con el contador) | **Alta** | El CPA máximo real (antes de IVA, que es el que muestra el Ads Manager) es CPA/1,19, unos **16 % más bajo**. Masajeador con r = 15 %: $41.886 → **$35.198**. Bandas: $20.240 → **$17.008** |
| F2 | Tasa de devolución del 10–20 % **sin respaldo**: Effi tiene 0 guías | Alta | Hay que sensibilizar a 25–30 % para tiendas nuevas. Masajeador con r = 30 % y con IVA: CPA máx **$23.055**. Soporte magnético: **$2.457**, que lo hace inviable |
| F3 | Flete de retorno igual al de ida, y flete plano sin seguro ni valor declarado | Media | Parametrizado en `Supuestos(flete_retorno=...)`. Se reemplaza con la tarifa real de la transportadora |
| F4 | Comisión COD del 3 % supuesta, sin mínimo fijo | Media | Las transportadoras suelen cobrar un % con un mínimo. Se reemplaza con la tarifa real |
| F5 | Faltan el GMF (4×1000) en retiros y los costos de la wallet o de retiro | Baja | Alrededor de 0,4 % del recaudo; se agrega cuando haya un flujo real |
| F6 | El "margen neto con CPA objetivo" es por construcción el 40 % del CPA máximo, no un dato de mercado | Baja (de presentación) | Hay que rotularlo como colchón y no como margen esperado |
| F7 | La columna "por entregado" del cálculo no se publicó y la base (pedido generado) no estaba destacada | Baja | Hay que declarar siempre la base del CPA |
| F8 | Supuesto de que la mercancía devuelta no se pierde | Media | Si el proveedor cobra roturas o reempaque, hay que restar C·tasa_daño en la rama "rechazado" |
| F9 | No incluye IVA o impuestos sobre la venta ni el régimen tributario del vendedor | Media | Depende del régimen fiscal; queda fuera del modelo hasta definirlo con el contador |

**Tabla corregida** (IVA del 19 % sobre la pauta; C = P/3; Fi = Fr = 20.000; k = 3 %). Los valores salen de `python3 scripts/modelo_financiero.py`:

| Producto | PVP | CPA máx 15 % | CPA máx 20 % | CPA máx 30 % |
|---|---|---|---|---|
| Masajeador cervical | $119.900 | $35.198 | $31.150 | $23.055 |
| Bandas de resistencia | $79.900 | $17.008 | $14.030 | $8.075 |
| Quita pelo (x2) | $69.900 | $12.460 | $9.750 | $4.329 |
| Corrector de postura | $69.900 | $12.460 | $9.750 | $4.329 |
| Soporte magnético (x2) | $64.900 | $10.187 | $7.610 | $2.457 |

**PVP mínimo** (C = P/3, con IVA) para un CPA máximo de $20.000: **$86.480** con r = 15 %, **$102.199** con r = 25 % y **$111.743** con r = 30 %. Para $30.000: $108.469, $127.120 y $138.444.

→ **Conclusión:** con IVA y devoluciones realistas, **solo los tickets de $100.000 o más son viables**. Los productos 3–5 del informe 01 deben subir el ticket (bundles) o descartarse.

**Qué funciona.** La estructura de la fórmula, el álgebra y los números publicados.

**Qué no funciona.** Los supuestos de IVA, devoluciones y tarifas reales.

**Solución propuesta.** Usar `scripts/modelo_financiero.py` como única fuente de cálculo, con IVA del 19 % por defecto, sensibilidad obligatoria a r = 25–30 % y tarifas reales de la transportadora una vez cotizadas.

**Costos o limitaciones.** Ninguno: es código local y no consume tokens.

---

## 5. Fuentes alternativas verificables

| Fuente | Qué aporta | Estado real desde aquí | Requisito |
|---|---|---|---|
| `WebSearch` (herramienta del agente) | Blogs, rankings, noticias de demanda | **Funciona** (se usó en el informe 01) | Ninguno; la calidad es secundaria |
| Web de Meta Ad Library (manual) | Anunciantes activos en CO y fecha de inicio | Funciona **para humanos** | Navegador del usuario |
| TikTok Creative Center (manual) | Top Ads y tendencias en CO | Funciona **para humanos** | Navegador del usuario (posible inicio de sesión) |
| Claude in Chrome | Las dos anteriores, asistidas | No probado en esta sesión | Extensión en el navegador del usuario |
| Mercado Libre Colombia (`api.mercadolibre.com`, sitio MCO) | Precios de mercado y competencia | **Bloqueado** (red); los endpoints de búsqueda pueden requerir OAuth (verificar) | Abrir el host y, posiblemente, una app de ML |
| Google Trends | Interés relativo por palabra clave en CO | **Bloqueado** (red); sin API pública estable | Abrir el host o consultarlo a mano |
| Catálogo del proveedor (Effi o Dropi) | Costo y stock reales | Solo desde la cuenta del usuario | Vinculación o exportación manual |
| Effi MCP (cuando haya ventas) | Devolución real, flete real, recaudo | **Funciona** (hoy vacío) | Operación real |

**Solución propuesta.** Mantener una plantilla CSV (`producto, fuente, url, fecha_consulta, anunciantes_activos, inicio_mas_antiguo, precio_visto`) que el usuario llena desde su navegador. Un script la ingiere y puntúa sin usar IA.

---

## 6. Costos: qué requiere IA y qué puede ejecutarse con código

| Tarea | Ejecutar con | Motivo |
|---|---|---|
| Lectura de Effi (artículos, costos, stock, guías) | **Código o llamadas MCP directas**, sin razonamiento | Datos estructurados; filtros fijos |
| Modelo financiero, escenarios y sensibilidad | **Código** (`scripts/modelo_financiero.py`) | Determinista; 0 tokens |
| Puntuación de 100 puntos (pesos fijos) | **Código** | Reglas cuantificables una vez que hay datos |
| Ingesta de CSV con evidencia de Meta y TikTok | **Código** | Parseo y conteo |
| Pruebas y regresiones | **Código** (pytest) | 0 tokens |
| Exclusiones (Invima, tallas, ilegales, perecederos) | **IA**, con una lista de reglas en código como prefiltro | Requiere juicio sobre la descripción del producto |
| Selección inicial de candidatos desde fuentes secundarias | **IA** (`WebSearch` y síntesis) | Texto no estructurado |
| Ángulos creativos y guiones | **IA** | Generativo |
| Redacción del informe final | **IA** sobre una tabla ya calculada por código | Hay que pasarle solo resultados, no datos crudos |

**Ahorro estimado.** Mover a código el cálculo, la puntuación y la ingesta elimina la mayor parte de las iteraciones del modelo. La IA queda solo para el juicio (exclusiones), la búsqueda secundaria y lo creativo. También conviene evitar llamadas MCP de listado amplias: usar filtros (`dropshipping_distribuidor=1`, `id`) y `por_pagina` pequeño.

---

## Acciones recomendadas (sin ejecutar; requieren decisión del usuario)

1. Vincular en Effi los candidatos con ticket alto (≥ $100.000, o en bundle) y confirmar el costo real.
2. Verificar a mano Meta Ad Library y TikTok Creative Center con la plantilla CSV, o activar Claude in Chrome.
3. Cotizar la tarifa real de flete, retorno y comisión COD con la transportadora o Effi, y cargarla en `Supuestos`.
4. Confirmar con el contador el IVA sobre la pauta y el régimen fiscal.
5. Reemitir el informe como **Informe 02** con el modelo corregido.
