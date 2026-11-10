#!/usr/bin/env python3
"""Generar muestras de voz VoxCPM2 (diseno por descripcion) para la microserie.

Carga el modelo UNA sola vez y genera una muestra por personaje del
manifiesto (muestras.json). Cada muestra usa la descripcion de voz en
ingles del personaje + su linea en espanol, con seed fija para que la
voz sea reproducible: descripcion + seed = lock de voz.

Uso:
    python scripts/generar_muestras.py --manifiesto muestras.json --out-dir muestras
    python scripts/generar_muestras.py --manifiesto muestras.json --out-dir muestras --personaje camila
    python scripts/generar_muestras.py --manifiesto muestras.json --out-dir muestras --dry-run
    python scripts/generar_muestras.py --manifiesto muestras.json --out-dir muestras --seed-base 100

Por que NO se usa la CLI `voxcpm design` aqui: cada invocacion de la CLI
carga el modelo completo (4.6 GB BF16) desde cero; 3 personajes serian
3 cargas. Con la API se carga una vez y se generan las 3 muestras.

Decisiones fijadas por la documentacion oficial (OpenBMB/VoxCPM):
- Modelo openbmb/VoxCPM2 (2B): es el UNICO de la familia con Voice Design
  y con espanol. VoxCPM-0.5B y VoxCPM1.5 NO tienen Voice Design y solo
  hablan chino/ingles (tabla oficial "Models & Versions").
- device="cpu", optimize=False: optimize=True es torch.compile; en CPU
  intentaria compilar el modelo de 2B con inductor (lento, puede fallar).
- load_denoiser=False: el denoiser (ZipEnhancer) es una descarga aparte
  de ModelScope y solo se usa para limpiar audios de referencia; en
  `design` no hay referencia, asi que no hace falta.
- cfg_value=2.0, inference_timesteps=10: defaults del README oficial.

Salida por personaje: <id>.wav (48 kHz, VoxCPM2) + manifiesto_corrida.json
con duraciones, tiempos de generacion y parametros. Si una muestra falla,
se sigue con las demas y el script termina con exit 1.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# El script se importa sin voxcpm instalado en --dry-run: el import va
# dentro de main() para que la prueba en seco no necesite el modelo.


def cargar_manifiesto(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        manifiesto = json.load(f)
    for p in manifiesto["personajes"]:
        for campo in ("id", "descripcion_voz_en", "linea_es", "seed"):
            if campo not in p or p[campo] in (None, ""):
                raise ValueError(f"Personaje sin {campo!r}: {p}")
    return manifiesto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifiesto", required=True, help="JSON con personajes, descripciones y lineas")
    parser.add_argument("--out-dir", required=True, help="Directorio de salida para los wavs")
    parser.add_argument("--personaje", default="todos",
                        help="ID del personaje a generar (camila, carmen, emilio) o 'todos'")
    parser.add_argument("--seed-base", type=int, default=None,
                        help="Si se da, desplaza todas las seeds (seed_final = seed_base + indice)")
    parser.add_argument("--device", default="cpu", help="Dispositivo torch (default: cpu)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo valida el manifiesto e imprime lo que se generaria, sin cargar el modelo")
    args = parser.parse_args()

    manifiesto = cargar_manifiesto(Path(args.manifiesto))
    fijos = manifiesto.get("parametros_fijos", {})
    personajes = manifiesto["personajes"]
    if args.personaje != "todos":
        personajes = [p for p in personajes if p["id"] == args.personaje]
        if not personajes:
            print(f"Personaje desconocido: {args.personaje}", file=sys.stderr)
            return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[voxcp2] modelo: {manifiesto.get('modelo')}")
    print(f"[voxcp2] personajes: {[p['id'] for p in personajes]}")
    for i, p in enumerate(personajes):
        seed = (args.seed_base + i) if args.seed_base is not None else p["seed"]
        print(f"[voxcp2] {p['id']}: seed={seed} linea={p['linea_es']!r}")

    if args.dry_run:
        print("[voxcp2] dry-run OK: manifiesto valido, nada generado.")
        return 0

    from voxcpm import VoxCPM

    t0 = time.perf_counter()
    print("[voxcp2] Cargando modelo (una sola vez)...", flush=True)
    model = VoxCPM.from_pretrained(
        manifiesto.get("modelo", "openbmb/VoxCPM2"),
        load_denoiser=fijos.get("load_denoiser", False),
        device=args.device,
        optimize=fijos.get("optimize", False),
    )
    print(f"[voxcp2] Modelo cargado en {time.perf_counter() - t0:.1f}s "
          f"(sample_rate={model.tts_model.sample_rate} Hz)", flush=True)

    import soundfile as sf

    resultados = []
    fallos = 0
    for i, p in enumerate(personajes):
        seed = (args.seed_base + i) if args.seed_base is not None else p["seed"]
        texto = f"({p['descripcion_voz_en']}){p['linea_es']}"
        salida = out_dir / f"{p['id']}.wav"
        print(f"[voxcp2] Generando {p['id']} (seed={seed})...", flush=True)
        t1 = time.perf_counter()
        try:
            wav = model.generate(
                text=texto,
                cfg_value=fijos.get("cfg_value", 2.0),
                inference_timesteps=fijos.get("inference_timesteps", 10),
                seed=seed,
            )
        except Exception as exc:  # noqa: BLE001 - seguir con el siguiente personaje
            print(f"[voxcp2] FALLO {p['id']}: {exc}", file=sys.stderr, flush=True)
            resultados.append({"id": p["id"], "ok": False, "error": str(exc)})
            fallos += 1
            continue
        duracion = len(wav) / model.tts_model.sample_rate
        sf.write(str(salida), wav, model.tts_model.sample_rate)
        gen_s = time.perf_counter() - t1
        rtf = gen_s / duracion if duracion > 0 else 0.0
        print(f"[voxcp2] {p['id']}: {salida} ({duracion:.2f}s de audio, "
              f"generado en {gen_s:.1f}s, RTF={rtf:.2f})", flush=True)
        resultados.append({
            "id": p["id"],
            "ok": True,
            "archivo": f"{p['id']}.wav",
            "duracion_s": round(duracion, 2),
            "tiempo_generacion_s": round(gen_s, 1),
            "rtf": round(rtf, 2),
            "seed": seed,
            "cfg_value": fijos.get("cfg_value", 2.0),
            "inference_timesteps": fijos.get("inference_timesteps", 10),
            "descripcion_voz_en": p["descripcion_voz_en"],
            "linea_es": p["linea_es"],
            "sample_rate_hz": model.tts_model.sample_rate,
        })

    manifiesto_corrida = {
        "modelo": manifiesto.get("modelo"),
        "licencia_modelo": manifiesto.get("licencia_modelo", "Apache-2.0"),
        "tiempo_total_s": round(time.perf_counter() - t0, 1),
        "resultados": resultados,
    }
    with open(out_dir / "manifiesto_corrida.json", "w", encoding="utf-8") as f:
        json.dump(manifiesto_corrida, f, ensure_ascii=False, indent=2)
    print(f"[voxcp2] Manifiesto de corrida en {out_dir / 'manifiesto_corrida.json'}")
    print(f"[voxcp2] Terminado: {len(resultados) - fallos}/{len(resultados)} muestras OK "
          f"en {time.perf_counter() - t0:.1f}s totales.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
