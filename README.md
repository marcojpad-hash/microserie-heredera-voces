# VoxCPM2 CPU — muestras de voz para "La heredera que vendieron"

Paquete de generación ya publicado en este repositorio (`main`):
`.github/workflows/voxcp2-cpu.yml`, `scripts/generar_muestras.py` y
`muestras.json`. Genera voces ficticias para Camila, Carmen y Don Emilio.
Las muestras son para que Marco las escuche y apruebe; **no cambian ningún
lock de voz**. Elena (`ef_dora`) y Adrián (`em_santa`) no se tocan.
Estado a 2026-11-10: el script y workflow están en GitHub; no hay evidencia
de una corrida VoxCPM2 ni de WAV generado/escuchado. No se debe disparar el
workflow hasta confirmar que la corrida #3 de SadTalker quedó resuelta.
La app GitHub conectada aquí no expone permiso/acción para `workflow_dispatch`;
el disparo, cuando se levante esa compuerta, se hace desde Actions en GitHub.

## Veredicto

| Pregunta | Respuesta |
|---|---|
| ¿La 0.5B sirve para esto? | **NO. Rotundamente no, por dos razones.** Verificadas en la tabla oficial "Models & Versions" del README de OpenBMB/VoxCPM (commit 300e426, 2026-11-10): **VoxCPM-0.5B NO tiene Voice Design** (celda "—") y **solo habla chino e inglés** (2 idiomas). VoxCPM1.5 (0.6B) está igual: sin Voice Design, solo zh/en. |
| ¿Qué versión sí sirve? | **Solo VoxCPM2 (2B)**: Voice Design ✅, 30 idiomas incluido español, 48 kHz, Apache-2.0. Es la que usa este workflow. |
| ¿Corre en CPU sin GPU? | **Sí, en principio.** La CLI y la API aceptan `--device cpu` (verificado en `src/voxcpm/cli.py` y `core.py` del repo). Pero **NO_VERIFICADO en ejecución**: nunca se ha corrido VoxCPM2 en CPU; la velocidad y la RAM reales solo se saben con la corrida de prueba. |
| ¿Cabe en el runner? | **Sí, en el repo público.** `ubuntu-24.04` en repo público = 4 vCPU, 16 GB RAM, 14 GB SSD (docs oficiales de GitHub). Pesos BF16 ~4.6 GB en RAM + runtime caben en 16 GB. **En repo privado serían 2 vCPU / 8 GB: ahí sería muy justo** (4.6 GB de pesos + overhead rozan el límite). El piloto es público, así que vale. |
| ¿Cabe en disco? | **Justo.** Modelo ~9.5 GB (verificado en la API de HF: `usedStorage: 9538100293`) + venv ~2.5 GB ≈ 12 GB de 14 GB. El workflow libera disco (quita dotnet, toolcache, Android, etc.) y aborta si quedan < 11 GB libres antes de descargar. |
| ¿Cuánto tarda la corrida? | **Estimado 15–30 min típico; hasta ~60 min en el peor caso.** Desglose: setup (Python + torch CPU + voxcpm) 5–10 min; descarga del modelo 9.5 GB, 2–5 min; carga del modelo en CPU 2–4 min; generación de 3 líneas (~15 s de audio) 2–10 min — el RTF en CPU es NO_VERIFICADO (en GPU RTX 4090 es ~0.30; en CPU se estima 5–30× más lento). El `generate()` reintenta hasta 3 veces si la salida sale mala, lo que puede triplicar la generación. Timeout del job: 120 min. |
| ¿Cuánto cuesta? | **$0.** Repo público: los runners estándar son gratis e ilimitados, no gastan los 2.000 min/mes. Sin secretos, sin login, sin tarjeta. |
| ¿Qué falta para dispararla? | Los archivos ya están publicados en ESTE repositorio: `.github/workflows/voxcp2-cpu.yml`, `scripts/generar_muestras.py` y `muestras.json`. Falta confirmar que la corrida #3 de SadTalker quedó resuelta. Después de esa confirmación: GitHub → Actions → “VoxCPM2 CPU — Muestras de voz” → Run workflow. La app GitHub conectada a esta sesión no ofrece `workflow_dispatch`; no se ha disparado desde aquí. |

## Archivos

| Archivo en GitHub (`main`) | Qué es | Estado |
|---|---|---|
| `.github/workflows/voxcp2-cpu.yml` | Workflow: Python 3.11, torch CPU, voxcpm, genera muestras, sube artifact `voxcp2-muestras` (7 días). Inputs: `personaje` (todos/camila/carmen/emilio), `seed_base` (0 = seeds del manifiesto). | Publicado en `main`. |
| `scripts/generar_muestras.py` | Carga el modelo **una sola vez** y genera las 3 muestras en el mismo proceso. Soporta `--personaje`, `--seed-base`, `--dry-run`. Escribe `muestras/<id>.wav` (48 kHz) + `manifiesto_corrida.json` con duraciones y RTF real. | Publicado en `main`. |
| `muestras.json` | Manifiesto: modelo, parámetros fijos, 3 personajes con descripción de voz (en), línea (es) y seed. | Publicado en `main`. |
| `README.md` | Instrucciones y estado del paquete. | Este archivo en `main`. |

## Las 3 voces diseñadas

Descripciones en inglés, como las pide el modelo (género, edad, tono,
emoción, ritmo). La línea se sintetiza en español; el modelo no necesita
etiqueta de idioma.

| Personaje | Descripción de voz (Voice Design) | Línea (es) | Seed |
|---|---|---|---|
| **Camila** (26, prima, novia) | A young woman in her mid-twenties, bright and sharp voice, confident and slightly arrogant tone, clear and crisp diction, moderately fast pace, cutting and dismissive when she speaks | "La novia soy yo, por si se te olvida." | 42 |
| **Carmen** (55, matriarca) | A mature woman in her mid-fifties, low and controlled voice, cold and authoritative tone, slow and deliberate pace, restrained, with quiet menace | "Elena, no hagas escándalo." | 43 |
| **Don Emilio** (65, notario) | An elderly man in his mid-sixties, thin and slightly trembling voice, slow and hesitant pace, quiet and formal tone, nervous and careful, as if afraid of saying too much | "Es auténtico. Es el testamento de tu abuelo." | 44 |

**Regla de lock:** descripción + seed = la voz. Si una muestra no suena
como el personaje, se regenera con otra seed (el README oficial dice que
Voice Design puede necesitar 1–3 intentos) y se anota la seed elegida.
Una vez que Marco aprueba una muestra, su descripción + seed quedan como
lock y no se tocan (regla de Marco 2026-11-10 ~00:28).

## Decisiones técnicas (todas con fuente)

- **VoxCPM2, no 0.5B.** Tabla oficial "Models & Versions" (OpenBMB/VoxCPM
  README): Voice Design ✅ solo en VoxCPM2; 0.5B y 1.5: "—". Idiomas:
  VoxCPM2 30 (español incluido, WER es 1.33% en el benchmark interno de
  30 idiomas); 0.5B/1.5: 2 (zh, en).
- **`optimize=False` (`--no-optimize`).** En `core.py`, `optimize=True`
  es `torch.compile` + un warm-up que genera una frase al cargar. En CPU
  compilar un modelo 2B con inductor es muy lento y puede fallar; se
  desactiva.
- **`load_denoiser=False`.** El denoiser (ZipEnhancer, `iic/speech_zipenhancer_ans_multiloss_16k_base`)
  es una descarga aparte de ModelScope y solo limpia audios de
  referencia; en `design` no hay referencia, así que no hace falta.
- **torch CPU instalado antes que voxcpm.** `pip install voxcpm` bajaría
  el wheel CUDA de torch (~2.5 GB) si torch no está ya instalado; por
  eso el workflow instala primero `torch torchaudio torchcodec` desde
  el índice CPU de PyTorch.
- **Python 3.11, ubuntu-24.04.** voxcpm exige Python ≥ 3.10 (< 3.13).
- **Modelo cargado una vez.** El script usa la API (`VoxCPM.from_pretrained`,
  `model.generate(text="(descripcion)linea", ...)`) en vez de 3 llamadas
  a la CLI, que recargarían el modelo cada vez.
- **Sin caché del modelo.** 9.5 GB ≈ el límite de 10 GB de caché por
  repo; no vale la pena. La descarga fresca de HF tarda 2–5 min.

## Riesgos conocidos (qué puede fallar en la primera corrida)

1. **OOM en RAM (medio).** Si el runner resulta ser el de repo privado
   (2 vCPU / 8 GB) en vez del público (4 vCPU / 16 GB), 4.6 GB de pesos
   BF16 + activaciones + overhead pueden matar el proceso. Mitigación:
   el workflow imprime `free -m` al inicio; si OOM, la salida es usar
   el repo público (ya lo es) o Kaggle.
2. **Disco lleno (medio).** 12 GB de 14 GB. Mitigación: paso de liberar
   disco + guarda de 11 GB antes de descargar. Si aun así falta, la
   salida es borrar el caché de pip (ya se usa `--no-cache-dir`) o
   quitar `ffmpeg` del paso de sistema.
3. **CPU muy lento (bajo-medio).** RTF en CPU NO_VERIFICADO. Si una
   muestra tarda > 10 min, el job tiene 120 min de timeout; el
   `manifiesto_corrida.json` dirá el RTF real para estimar la producción
   completa (un episodio ~45 s de diálogo por personaje).
4. **La descripción en inglés no cuaja en español (bajo).** El diseño de
   voz se evaluó oficialmente solo en ZH y EN (InstructTTSEval); que la
   descripción en inglés controle bien una voz que habla español no está
   verificado en la documentación. Si las muestras salen con la voz
   correcta pero el español suena raro, o la descripción no se nota:
   **Plan B** — generar la voz diseñada con texto en inglés, usar ese
   wav como `--reference-audio` y clonar las líneas en español con
   `--control` (clonación controlable, también solo en VoxCPM2).
5. **Voice Design varía entre corridas (conocido).** El README oficial
   avisa: "puede que tengas que generar 1–3 veces para obtener la voz
   deseada". Por eso las seeds son fijas y el input `seed_base` permite
   probar otra tanda sin tocar el manifiesto.

## Fuentes verificadas 2026-11-10

- OpenBMB/VoxCPM README (commit 300e426): tabla "Models & Versions",
  Voice Design, CLI, requisitos Python ≥ 3.10 / torch ≥ 2.5 / CUDA ≥ 12.
- `src/voxcpm/cli.py` (main): default `openbmb/VoxCPM2`, `--device`
  auto/cpu/mps/cuda, `--control`, `--cfg-value` 2.0, `--inference-timesteps` 10.
- `src/voxcpm/core.py` (main): `optimize` = torch.compile + warm-up;
  denoiser ZipEnhancer por defecto; `device` explícito acepta `"cpu"`.
- HF API `openbmb/VoxCPM2`: BF16 2.29B parámetros, `usedStorage`
  9.538.100.293 bytes (~9.5 GB), licencia apache-2.0, `es` en idiomas.
- GitHub Docs "GitHub-hosted runners": público 4 vCPU/16 GB, privado
  2 vCPU/8 GB, disco 14 GB; runners estándar gratis e ilimitados en
  repos públicos.
- Biblia: `~/workspace/microseries/piloto/la-heredera-que-vendieron/BIBLIA.md`
  (§6 locks, §16 restricción de voces).
