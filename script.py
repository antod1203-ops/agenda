import base64
import json
from datetime import datetime
import requests
from typing import Union  # Importación añadida para compatibilidad de tipos


class AgendaScraper:
    """Clase encargada de raspar, normalizar y unificar agendas de eventos deportivos."""

    # --- CONFIGURACIÓN DE LA CLASE ---
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    TIMEOUT = 15

    DEPORTES_KEYWORDS = {
        "F1": ["f1", "formula 1", "formula uno", "gp ", "grand prix", "verstappen", "hamilton", "leclerc", "alonso", "perez", "sainz"],
        "Tenis": ["roland garros", "tenis", "tennis", "wimbledon", "atp", "wta", "us open", "australian open", "nadal", "alcaraz", "djokovic", "sinner", "itf", "challenger", "masters 1000"],
        "Béisbol": ["mlb", "béisbol", "beisbol", "giants", "cubs", "yankees", "dodgers", "red sox", "astros", "lidom", "lbpv", "home run", "world series"],
        "Baloncesto": ["nba", "básquet", "basquet", "basketball", "euroleague", "euroliga", "acb", "fiba", "wnba", "lakers", "celtics", "warriors", "bulls"],
        "UFC/MMA": ["ufc", "mma", "bellator", "pfl", "one championship", "knockout", "ko/tko", "main card", "prelims", "pesajes"],
        "MotoGP": ["motogp", "moto2", "moto3", "superbike", "marquez", "bagnaia", "quartararo"],
        "Ciclismo": ["tour de france", "giro d'italia", "vuelta a españa", "ciclismo", "cycling", "uci worldtour", "pogačar", "vingegaard"],
        "Fútbol": ["laliga", "premier league", "serie a", "bundesliga", "ligue 1", "champions league", "ucl", "europa league", "libertadores", "sudamericana", "mls", "liga mx", "ligamx", "fifa", "uefa", "conmebol", "real madrid", "barcelona", "manchester", "juventus", "psg", "boca juniors", "river plate"]
    }

    def __init__(self, fecha_defecto: str = None):
        self.fecha_defecto = fecha_defecto or datetime.now().strftime("%Y-%m-%d")
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    # --- MÉTODOS DE UTILIDAD (UTILITIES) ---

    @staticmethod
    def extraer_url_limpia(url_completa: str) -> str:
        """Elimina prefijos de redirección y decodifica Base64 si es necesario."""
        if not url_completa or not isinstance(url_completa, str):
            return ""
        
        contenido_url = url_completa.strip()
        if "?r=" in contenido_url:
            _, contenido_url = contenido_url.split("?r=", 1)
            contenido_url = contenido_url.strip()
            
        if contenido_url.startswith(("http://", "https://")):
            return contenido_url
            
        try:
            # Añade el padding necesario para Base64 de forma segura
            b64_fixed = contenido_url + "=" * ((4 - len(contenido_url) % 4) % 4)
            return base64.b64decode(b64_fixed).decode('utf-8', errors='ignore').strip()
        except Exception:
            return contenido_url

    @classmethod
    def obtener_categoria_optima(cls, titulo: str, cat_original: str) -> str:
        """Asigna el deporte idóneo basándose en palabras clave."""
        if not titulo:
            return "Otros Deportes"
            
        titulo_lower = titulo.lower()
        
        for categoria, claves in cls.DEPORTES_KEYWORDS.items():
            if any(clave in titulo_lower for clave in claves):
                return categoria
            
        if "vs" in titulo_lower or " v " in titulo_lower:
            return "Fútbol"
            
        if not cat_original or str(cat_original).lower() in ["other", "futbol", "otros", "none"]:
            return "Otros Deportes"
            
        return str(cat_original).strip().capitalize()

    # Se cambió el type hint 'list | dict | None' por 'Union[list, dict, None]' para compatibilidad
    def _fetch_json(self, url: str) -> Union[list, dict, None]:
        """Realiza peticiones HTTP seguras y retorna el JSON mapeado."""
        try:
            print(f"Descargando desde: {url}...")
            response = self.session.get(url, timeout=self.TIMEOUT)
            if response.status_code == 200:
                return response.json()
            print(f"Error {response.status_code} al conectar con {url}")
        except Exception as e:
            print(f"No se pudo acceder a {url}. Error: {e}")
        return None

    # --- PARSERS DE FUENTES (MÉTODOS PRIVADOS) ---

    def _parse_streamtp(self, data: Union[list, dict]) -> list:
        eventos = []
        lista_eventos = data.get("events", []) if isinstance(data, dict) else data or []
        
        for item in lista_eventos:
            titulo = " ".join(item.get("title", "").split()).strip() or "Evento sin título"
            cat_orig = item.get("category", "")
            
            evento = {
                "title": titulo,
                "fecha": item.get("fecha") or item.get("date") or self.fecha_defecto,
                "time": item.get("time") or "00:00",
                "category": self.obtener_categoria_optima(titulo, cat_orig),
                "featured": False,  # Cambiado a False
                "canales": []
            }
            
            for link_item in item.get("links", []):
                url_sucia = link_item.get("url", "")
                link_final = self.extraer_url_limpia(url_sucia)
                
                canal_sugerido = link_final.split("stream=")[-1].upper() if "stream=" in link_final else ""
                if not canal_sugerido:
                    canal_sugerido = link_item.get("server", "").strip()
                
                idioma_label = (link_item.get("lang", {}) or {}).get("label", "").capitalize()
                
                evento["canales"].append({
                    "nombre": canal_sugerido or idioma_label or "Opción",
                    "link": link_final
                })
                
            if not evento["canales"]:
                evento["canales"].append({"nombre": "Próximamente", "link": ""})
                
            eventos.append(evento)
        return eventos

    def _parse_la18hd(self, data: list) -> list:
        eventos = []
        for item in (data or []):
            titulo = " ".join(item.get("title", "").split()).strip() or "Evento sin título"
            link_final = self.extraer_url_limpia(item.get("link", ""))
            canal_sugerido = link_final.split("stream=")[-1].capitalize() if "stream=" in link_final else ""
            
            eventos.append({
                "title": titulo,
                "fecha": item.get("date") or item.get("fecha") or self.fecha_defecto,
                "time": item.get("time") or "00:00",
                "category": self.obtener_categoria_optima(titulo, item.get("category", "")),
                "featured": False,  # Cambiado a False
                "canales": [{
                    "nombre": canal_sugerido or item.get("language") or "Opción",
                    "link": link_final
                }]
            })
        return eventos

    def _parse_streamhdx(self, data: dict) -> list:
        eventos = []
        for dia in (data or {}).get("dias", []):
            fecha_iso = dia.get("fecha_iso") or self.fecha_defecto
            for ev in dia.get("eventos", []):
                titulo = " ".join(ev.get("titulo", "").split()).strip() or "Evento sin título"
                
                evento = {
                    "title": titulo,
                    "fecha": fecha_iso,
                    "time": ev.get("hora") or "00:00",
                    "category": self.obtener_categoria_optima(titulo, ev.get("categoria", "")),
                    "featured": False,
                    "canales": []
                }
                
                for canal in ev.get("canales", []):
                    evento["canales"].append({
                        "nombre": canal.get("nombre", "").strip() or "Opción",
                        "link": self.extraer_url_limpia(canal.get("url", ""))
                    })
                eventos.append(evento)
        return eventos

    def _parse_pltvhd(self, data: dict) -> list:
        eventos = []
        for item in (data or {}).get("data", []):
            attrs = item.get("attributes", {})
            titulo = " ".join(attrs.get("diary_description", "").split()).strip() or "Evento sin título"
            
            hora_corta = "00:00"
            if attrs.get("diary_hour"):
                hora_corta = ":".join(attrs["diary_hour"].split(":")[:2])
                
            fecha_evento = attrs.get("date_diary") or self.fecha_defecto
            pais_idioma = ((attrs.get("country", {}) or {}).get("data", {}) or {}).get("attributes", {}).get("name", "")
            embeds = (attrs.get("embeds", {}) or {}).get("data", [])
            
            evento = {
                "title": titulo,
                "fecha": fecha_evento,
                "time": hora_corta,
                "category": self.obtener_categoria_optima(titulo, ""),
                "featured": False,  # Cambiado a False
                "canales": []
            }
            
            if embeds:
                for emb in embeds:
                    emb_attr = emb.get("attributes", {})
                    evento["canales"].append({
                        "nombre": emb_attr.get("embed_name", "").strip() or pais_idioma or "Opción",
                        "link": self.extraer_url_limpia(emb_attr.get("embed_iframe", ""))
                    })
            else:
                evento["canales"].append({"nombre": pais_idioma or "Opción", "link": ""})
                
            eventos.append(evento)
        return eventos

    # --- CORE PROCESSOR ---

    def procesar_agendas(self, archivo_salida: str = "eventos.json"):
        """Método principal que coordina las descargas, unifica y guarda los datos."""
        eventos_crudos = []
        
        endpoints = [
            {"url": "https://streamtp.sbs/wc.json", "parser": self._parse_streamtp},
            {"url": "https://la20hd.com/eventos/json/agenda123.json", "parser": self._parse_la18hd},
            {"url": "https://streamhdx.com/eventos.json", "parser": self._parse_streamhdx},
            {"url": "https://pltvhd.com/diaries.json", "parser": self._parse_pltvhd}
        ]
        
        # Extracción
        for target in endpoints:
            data = self._fetch_json(target["url"])
            if data is not None:
                try:
                    eventos_extraidos = target["parser"](data)
                    eventos_crudos.extend(eventos_extraidos)
                except Exception as parse_err:
                    print(f"Error parseando {target['url']}: {parse_err}")

        if not eventos_crudos:
            print("\n[!] No se pudieron extraer eventos de ninguna fuente.")
            return

        # Agrupación Inteligente para evitar duplicados
        agenda_agrupada = {}
        for ev in eventos_crudos:
            clave_evento = (ev["title"].lower(), ev["fecha"], ev["time"])
            
            if clave_evento not in agenda_agrupada:
                agenda_agrupada[clave_evento] = {
                    "title": ev["title"],
                    "fecha": ev["fecha"],
                    "time": ev["time"],
                    "category": ev["category"],
                    "featured": False,  # Forzado a False aquí también por seguridad
                    "canales": []
                }
            
            urls_existentes = {c["link"] for c in agenda_agrupada[clave_evento]["canales"] if c["link"]}
            for canal in ev["canales"]:
                if not canal["link"] or canal["link"] not in urls_existentes:
                    agenda_agrupada[clave_evento]["canales"].append(canal)
                    if canal["link"]:
                        urls_existentes.add(canal["link"])

        # Ordenar canales alfabéticamente dentro de cada evento
        lista_final = list(agenda_agrupada.values())
        for ev in lista_final:
            ev["canales"] = sorted(ev["canales"], key=lambda c: str(c["nombre"]).lower())

        # Ordenamiento global: Fecha -> Hora -> Título
        print("\nOrganizando y ordenando la agenda unificada...")
        eventos_ordenados = sorted(
            lista_final,
            key=lambda x: (x["fecha"], x["time"], x["title"].lower())
        )

        # Escritura de resultados
        try:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(eventos_ordenados, f, ensure_ascii=False, indent=4)
            print(f"\n[Proceso Completado con Éxito]")
            print(f"Se han guardado {len(eventos_ordenados)} eventos únicos en '{archivo_salida}'.")
        except IOError as e:
            print(f"Error escribiendo el archivo de salida: {e}")


if __name__ == "__main__":
    # Inicializa y ejecuta el scraper
    scraper = AgendaScraper()
    scraper.procesar_agendas()
