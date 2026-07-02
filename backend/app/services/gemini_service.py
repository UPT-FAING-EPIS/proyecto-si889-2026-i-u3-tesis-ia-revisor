import hashlib
import json
import logging
import math
import re
import time
import unicodedata
from collections.abc import Generator

import httpx
from google import genai
from google.genai import types

from app.core.academic_catalog import (
    build_fallback_problem_suggestions,
    build_problem_suggestion_context,
    format_academic_context,
)
from app.core.config import get_settings


SYSTEM_PROMPT = """
Eres un asesor de tesis estricto pero util.
Reglas:
1) Responde en espanol claro y profesional.
2) Basa tu respuesta en los fragmentos de tesis proporcionados.
3) Si no hay suficiente evidencia, dilo explicitamente.
4) Da recomendaciones accionables para mejorar redaccion, metodo y rigor academico.
5) Evita inventar datos.
6) No inicies con saludos, presentaciones personales ni frases de cortesia.
""".strip()

THESIS_REVIEW_SYSTEM_PROMPT = """
Asesor y Revisor de Tesis - FAING

Rol e Identidad:
Eres el "Asesor Virtual FAING", un agente de Inteligencia Artificial especializado en la revision,
correccion y asesoria metodologica de proyectos de investigacion, trabajos de bachiller,
tesis de titulacion y articulos de revision.

Tu marco de referencia estricto y absoluto es el "Manual para el desarrollo de trabajos de
investigacion (2022)" de la Facultad de Ingenieria de la Universidad Privada de Tacna (UPT).

No tienes emociones ni experiencias personales, pero tu tono debe ser empatico, alentador,
profesional y academicamente riguroso.

Tu objetivo no es escribir la tesis por el estudiante, sino guiarlo para que alcance la excelencia
metodologica y formal exigida por la universidad.

Directrices Generales de Interaccion:
1) Metodo Socratico:
- No redactes parrafos completos de la tesis para el estudiante.
- Senala el error.
- Explica por que es incorrecto segun el manual.
- Haz preguntas guia para que el estudiante mejore su propia redaccion.

2) Rigor Formativo:
- Se implacable con el plagio y la falta de coherencia logica.
- Exige siempre citas correctas.

3) Formatos de Graduacion:
- Adapta tu revision dependiendo de si el estudiante esta elaborando un Trabajo de
    Investigacion (Bachiller), un Articulo de Revision (Bachiller), una Tesis formato tradicional
    (Titulo) o una Tesis formato Articulo Cientifico (IMRD).

Reglas de Revision Estructural (Basadas en el Manual FAING):
1. Titulo y Matriz de Consistencia:
- El titulo debe ser informativo, especifico y tener menos de 20 palabras.
- Prohibe el uso de abreviaciones o jergas en el titulo.
- Evalua siempre la Matriz de Consistencia.
- Exige una alineacion perfecta entre el Problema General, el Objetivo General y la Hipotesis General.

2. Planteamiento del Problema:
- Exige que la descripcion del problema vaya de lo general a lo particular, sustentada con citas.
- Verifica que la formulacion termine en preguntas claras (una general y maximo tres especificas)
    que incluyan las variables de estudio.
- Los objetivos deben responder exactamente a las preguntas planteadas y estar redactados con
    verbos en infinitivo (ej. determinar, evaluar, analizar) a nivel de plan.

3. Marco Teorico y Referencias:
- Exige que los antecedentes provengan de revistas cientificas indexadas (articulos cientificos)
    y tengan una antiguedad recomendada de 5 a 10 anos.
- Supervisa estrictamente el uso de las Normas APA (edicion vigente) para todas las citas en
    el texto y la lista de referencias bibliograficas.
- Verifica que la Tesis final o Trabajo de Investigacion tenga un minimo de 25 a 35 referencias
    (o no menos de 30 para formato articulo cientifico).

4. Marco Metodologico:
- Asegurate de que el estudiante defina claramente el Tipo de Estudio (Basico o Aplicado),
    el Nivel de Investigacion (Exploratorio, Descriptivo, Correlacional, Explicativo,
    Predictivo o Aplicativo) y el Diseno (Experimental o No experimental).
- Exige una delimitacion clara de la poblacion y el metodo de calculo de la muestra
    para reducir la variabilidad.
- Evalua si las tecnicas estadisticas propuestas (ej. t de Student, ANOVA,
    pruebas no parametricas, regresion) son las correctas para el tipo de variables
    (cuantitativas/cualitativas) y las hipotesis planteadas.

5. Resultados y Discusiones (Para informes finales):
- Rechaza cualquier resultado que contenga opiniones, juicios de valor o justificaciones.
- Verifica que la informacion de Tablas y Figuras no se repita en el texto.
- Las Tablas deben seguir el formato APA (sin lineas horizontales divisorias internas)
    y las Figuras no deben estar saturadas.
- En la seccion de Discusion, exige que el estudiante contraste sus hallazgos con los
    antecedentes citados en el Marco Teorico y argumente el rechazo o no rechazo de las hipotesis.

6. Conclusiones y Recomendaciones:
- Asegurate de que no se presenten nuevos resultados en las conclusiones.
- Debe haber tantas conclusiones como objetivos formulados.
- Las recomendaciones deben ser factibles y sugerir futuras lineas de investigacion
    derivadas del estudio.

Reglas Operativas de Respuesta:
- Responde siempre en espanol.
- Basa tu evaluacion solo en evidencia disponible en el documento.
- Si falta informacion, declaralo explicitamente y pide evidencia puntual.
- Entrega observaciones concretas por seccion y prioriza mejoras por impacto.
- No inventes citas, datos, autores ni resultados.
- No inicies con saludos, presentaciones ni texto introductorio personal.
- Empieza directamente en la seccion "1) Veredicto general".
""".strip()

THESIS_PLAN_SYSTEM_PROMPT = """
Asesor Virtual para Plan de Tesis UPT

Objetivo:
- Acompanar al estudiante desde una idea inicial hasta un plan de tesis coherente,
  segun la facultad y carrera seleccionadas.
- Antes de redactar el plan, realizar una entrevista metodologica suficiente.
- Cuando haya informacion suficiente, construir o actualizar el plan siguiendo la
  estructura normativa de la facultad.

Reglas:
- Responde en espanol claro, academico y directo.
- No inventes datos, autores, cifras, lugares, poblaciones ni referencias.
- Si falta informacion, propone un borrador razonable marcado como "por validar" y pregunta solo lo indispensable.
- Mantiene alineacion estricta entre problema general, objetivo general, hipotesis general,
  problemas especificos, objetivos especificos, hipotesis especificas, variables e indicadores.
- Para el plan, usa verbos en infinitivo en los objetivos.
- Considera que la hipotesis es pertinente solo cuando el enfoque y nivel lo justifiquen.
- Exige APA vigente, antecedentes cientificos actualizados y matriz de consistencia.
- No respondas con tareas vacias como "confirma titulo". Debes ofrecer 2 a 4 alternativas de titulo
  correctamente formuladas, variables tentativas, objetivos y matriz preliminar para que el estudiante valide.
- Si hay referencias candidatas entregadas por el sistema, usalas como antecedentes posibles y aclara que
  deben verificarse en texto completo antes de citarlas definitivamente.
- Este flujo no usa PDFs, documentos cargados ni sesiones de preguntas sobre PDF. Trabaja solo con la idea
  y las respuestas escritas en el historial del plan de tesis.
- No inicies con saludos ni presentaciones.
""".strip()

THESIS_SYSTEM_PROMPT = """
Asesor Virtual para Redaccion de Tesis UPT

Objetivo:
- Convertir un plan de tesis ya generado en un borrador de tesis coherente, formal y adaptado
  a la facultad y carrera del estudiante.
- Respetar la normativa, el enfoque metodologico y el tipo de entregable esperado por la carrera.
- Mantener continuidad estricta con el titulo, problema, objetivos, variables, metodologia,
  poblacion, instrumentos y referencias del plan fuente.

Reglas:
- Responde en espanol academico, directo y sin saludos.
- No cambies el tema ni la carrera del plan fuente.
- No inventes datos empiricos recolectados, autores, DOI, resultados estadisticos ni cifras reales.
- Si el plan no contiene datos ejecutados, redacta resultados como propuesta tecnica, matriz de
  resultados esperados, estructura de analisis o evidencia pendiente de levantamiento, segun la carrera.
- En carreras proyectuales o aplicadas, desarrolla la propuesta, prototipo, diseno, modelo,
  programa, intervencion o plan con criterio tecnico y realista.
- En carreras clinicas, psicologicas, educativas, empresariales o economicas, diferencia claramente
  entre resultados obtenidos y resultados esperados si el plan no aporta una base de datos real.
- Usa APA vigente y referencias verificables. Si una referencia es candidata, no le atribuyas hallazgos
  empiricos especificos que no esten disponibles.
- Mantiene alineacion estricta entre problema, objetivos, hipotesis/categorias, variables,
  metodologia, resultados/propuesta, conclusiones y recomendaciones.
- La misma instruccion debe funcionar con Gemini o DeepSeek sin depender de rasgos del proveedor.
""".strip()

THESIS_PLAN_MANUAL_SECTIONS = (
    "1. Datos generales: titulo, area y linea de investigacion, autor, asesor",
    "2. El problema de investigacion: descripcion, formulacion, justificacion, objetivos, hipotesis, variables, tipo y nivel",
    "3. Marco teorico: antecedentes, bases teoricas, definicion de terminos",
    "4. Marco metodologico: diseno, acciones, materiales/instrumentos, poblacion/muestra, analisis de datos",
    "5. Aspectos administrativos: cronograma, recursos humanos, presupuesto y financiamiento",
    "6. Referencias bibliograficas en APA vigente",
    "7. Anexos: matriz de consistencia",
)

THESIS_PLAN_COMPLETE_STAGE_PREFIX = "DOCUMENTO ACADEMICO COMPLETO - ETAPA"
THESIS_COMPLETE_STAGE_PREFIX = "TESIS COMPLETA - ETAPA"
THESIS_PLAN_COMPLETE_SECTIONS = (
    {
        "id": "datos_generales",
        "title": "I. DATOS GENERALES",
        "focus": (
            "Completar la caratula interna y los datos generales del plan. "
            "El titulo debe quedar formalmente redactado, sin la etiqueta repetitiva 'por validar'. "
            "El area, linea, autor y asesor deben tomarse de los datos formales si existen; "
            "si falta un dato, usa 'dato pendiente de registro' una sola vez, no placeholders entre corchetes."
        ),
        "required_output": (
            "Incluye 1.1 Titulo, 1.2 Area de investigacion, 1.3 Linea de investigacion, "
            "1.4 Autor(es), 1.5 Asesor. Agrega una breve nota de consistencia del titulo "
            "explicando variable, unidad de analisis, espacio y tiempo."
        ),
    },
    {
        "id": "problema_justificacion",
        "title": "II. EL PROBLEMA DE INVESTIGACION",
        "focus": (
            "Desarrollar el problema con redaccion discursiva, no en viñetas sueltas. "
            "La justificacion e importancia debe unir perspectiva practica, teorica, social, "
            "economica y de seguridad de la informacion en parrafos academicos."
        ),
        "required_output": (
            "Incluye 2.1 Descripcion del problema en 5 a 7 parrafos, 2.2 Formulacion del problema "
            "general y especificos, 2.3 Justificacion e importancia en parrafos, 2.4 Objetivos, "
            "2.5 Hipotesis y 2.6 Tipo y nivel de investigacion. Mantiene alineacion pregunta-objetivo-hipotesis."
        ),
    },
    {
        "id": "operacionalizacion",
        "title": "2.7 OPERACIONALIZACION DE VARIABLES",
        "focus": (
            "Crear una matriz profunda como tabla academica, no una tabla basica. "
            "Debe incluir definicion conceptual, definicion operacional, dimensiones, indicadores, "
            "escala, tecnica de recoleccion, instrumento y fuente de datos."
        ),
        "required_output": (
            "Presenta Tabla 1. Matriz de operacionalizacion de variables. "
            "Usa columnas: Variable, definicion conceptual, definicion operacional, dimensiones, "
            "indicadores, escala de medicion, tecnica/metodo de recoleccion, instrumento/fuente. "
            "Incluye al menos una variable independiente y cuatro indicadores dependientes coherentes."
        ),
    },
    {
        "id": "marco_teorico",
        "title": "III. MARCO TEORICO",
        "focus": (
            "Redactar marco teorico desarrollado. Los antecedentes no deben estar vacios ni ser ficticios. "
            "Usa referencias candidatas y redacta sintesis prudentes; si una fuente requiere verificacion, "
            "declara 'referencia candidata para verificacion' sin inventar resultados especificos."
        ),
        "required_output": (
            "Incluye 3.1 Antecedentes de la investigacion con minimo cinco parrafos, "
            "3.2 Bases teoricas con subsecciones numeradas 3.2.1, 3.2.2, etc.; "
            "incluye normas de citacion de tablas, figuras y ecuaciones; "
            "3.3 Definicion de terminos con subdivisiones 3.3.1 a 3.3.10."
        ),
    },
    {
        "id": "metodologia",
        "title": "IV. MARCO METODOLOGICO",
        "focus": (
            "Consolidar la metodologia con diseno, acciones, instrumentos, poblacion, muestra "
            "y tecnicas de analisis alineadas a la operacionalizacion."
        ),
        "required_output": (
            "Incluye 4.1 Diseño de investigacion, 4.2 Acciones y actividades, "
            "4.3 Materiales e instrumentos, 4.4 Poblacion y muestra, "
            "4.5 Tecnicas de procesamiento y analisis de datos. "
            "Propone formulas, criterios de seleccion y estadistica de contraste cuando corresponda."
        ),
    },
    {
        "id": "administrativos_referencias",
        "title": "V. ASPECTOS ADMINISTRATIVOS Y VI. REFERENCIAS BIBLIOGRAFICAS",
        "focus": (
            "Completar cronograma, recursos, presupuesto y referencias. La seccion de referencias "
            "no debe quedar en blanco ni decir 'por completar'."
        ),
        "required_output": (
            "Incluye 5.1 Cronograma como tabla, 5.2 Recursos humanos, 5.3 Presupuesto y financiamiento. "
            "Luego desarrolla VI. Referencias bibliograficas en formato APA 7. "
            "Usa referencias candidatas, normativa de la facultad, normas tecnicas o legales pertinentes."
        ),
    },
    {
        "id": "anexos",
        "title": "ANEXOS",
        "focus": (
            "Ordenar los anexos en una seccion formal exclusiva. La matriz de consistencia no debe quedar "
            "flotando con numeracion incorrecta."
        ),
        "required_output": (
            "Incluye ANEXOS, Anexo 1 - Tabla 2. Matriz de consistencia, con columnas problema, objetivo, "
            "hipotesis, variables, dimensiones, indicadores y metodologia. "
            "Incluye Anexo 2 - Instrumentos de recoleccion y Anexo 3 - Estructura de log/auditoria si aplica."
        ),
    },
)

THESIS_COMPLETE_SECTIONS = (
    {
        "id": "preliminares_resumen",
        "title": "PRELIMINARES, RESUMEN E INTRODUCCION",
        "focus": (
            "Abrir la tesis con datos formales, resumen, abstract, palabras clave e introduccion. "
            "El resumen debe expresar problema, objetivo, metodologia, propuesta o resultados esperados "
            "sin inventar resultados empiricos no levantados."
        ),
        "required_output": (
            "Incluye caratula textual, titulo, autor(es), asesor, facultad/carrera, resumen, abstract, "
            "palabras clave, keywords e introduccion. La introduccion debe cerrar con la organizacion "
            "capitular de la tesis."
        ),
    },
    {
        "id": "capitulo_i_problema",
        "title": "CAPITULO I. PLANTEAMIENTO DEL PROBLEMA",
        "focus": (
            "Convertir el problema del plan en un capitulo discursivo de tesis. Debe contextualizar "
            "desde Tacna, Peru o el ambito definido, explicar causas, efectos, brecha y pertinencia "
            "disciplinar."
        ),
        "required_output": (
            "Incluye realidad problematica o planteamiento, formulacion del problema general y especificos, "
            "objetivo general y especificos, justificacion, importancia, alcances, limitaciones e hipotesis "
            "o supuestos/categorias si corresponde."
        ),
    },
    {
        "id": "capitulo_ii_marco_teorico",
        "title": "CAPITULO II. MARCO TEORICO",
        "focus": (
            "Desarrollar antecedentes, bases teoricas, marco conceptual, normativo y contextual. "
            "Debe estar adaptado al campo de la carrera y al entregable del plan."
        ),
        "required_output": (
            "Incluye antecedentes internacionales, nacionales y locales cuando sea razonable, bases teoricas "
            "con subsecciones, definicion de terminos, marco normativo o tecnico y modelo teorico/conceptual."
        ),
    },
    {
        "id": "capitulo_iii_metodologia",
        "title": "CAPITULO III. METODOLOGIA",
        "focus": (
            "Desarrollar la metodologia final a partir del plan. Debe precisar tipo, nivel, diseno, "
            "ambito, poblacion, muestra, variables/categorias, instrumentos, procedimiento, validez, "
            "confiabilidad, etica y analisis de datos."
        ),
        "required_output": (
            "Incluye matriz de operacionalizacion o categorias, poblacion y muestra, criterios de inclusion "
            "y exclusion cuando correspondan, tecnicas e instrumentos, procedimiento de recoleccion, "
            "procesamiento, analisis estadistico o tecnico y consideraciones eticas."
        ),
    },
    {
        "id": "capitulo_iv_resultados_propuesta",
        "title": "CAPITULO IV. RESULTADOS, DESARROLLO O PROPUESTA",
        "focus": (
            "Construir el capitulo central segun la carrera: resultados y analisis si el estudio es "
            "empirico; desarrollo/prototipo/diseno/propuesta si es aplicado o proyectual. No inventar "
            "datos reales; usar resultados esperados, escenarios de validacion o tablas de analisis "
            "cuando el plan no contenga datos ejecutados."
        ),
        "required_output": (
            "Incluye diagnostico, desarrollo de la propuesta o resultados esperados, tablas/figuras en formato "
            "Markdown cuando ayuden, criterios de validacion, indicadores de evaluacion y lectura tecnica "
            "adaptada a la carrera."
        ),
    },
    {
        "id": "capitulo_v_discusion",
        "title": "CAPITULO V. DISCUSION",
        "focus": (
            "Redactar la discusion conectando el problema, teoria, metodologia y resultados/propuesta. "
            "Debe reconocer limites cuando aun no hay datos reales."
        ),
        "required_output": (
            "Incluye contraste con antecedentes, interpretacion por objetivos, implicancias teoricas y "
            "practicas, limitaciones metodologicas y consecuencias para la facultad/carrera."
        ),
    },
    {
        "id": "conclusiones_recomendaciones",
        "title": "CONCLUSIONES Y RECOMENDACIONES",
        "focus": (
            "Cerrar la tesis con conclusiones alineadas a objetivos y recomendaciones factibles. "
            "No introducir datos nuevos."
        ),
        "required_output": (
            "Incluye conclusiones numeradas segun los objetivos, recomendaciones para actores concretos, "
            "lineas futuras de investigacion y aportes esperados de la tesis."
        ),
    },
    {
        "id": "referencias_anexos",
        "title": "REFERENCIAS Y ANEXOS",
        "focus": (
            "Ordenar referencias y anexos finales. Debe incluir instrumentos, matriz de consistencia y "
            "evidencias necesarias para ejecutar o sustentar la tesis."
        ),
        "required_output": (
            "Incluye referencias en APA 7, anexos con matriz de consistencia, matriz de operacionalizacion "
            "o categorias, instrumentos, guia de validacion, cronograma de ejecucion y anexos tecnicos "
            "propios de la carrera."
        ),
    },
)

THESIS_PLAN_REQUIRED_FIELDS = (
    {
        "label": "Tema o idea central",
        "keywords": ("tema", "idea", "titulo", "proyecto", "tesis", "sistema", "modelo", "aplicacion"),
    },
    {
        "label": "Problema observable",
        "keywords": ("problema", "deficiencia", "dificultad", "falla", "necesidad", "brecha", "causa", "efecto"),
    },
    {
        "label": "Contexto o delimitacion",
        "keywords": ("empresa", "universidad", "institucion", "ciudad", "distrito", "facultad", "periodo", "semestre", "contexto"),
    },
    {
        "label": "Unidad de analisis o poblacion",
        "keywords": ("usuarios", "estudiantes", "trabajadores", "clientes", "pacientes", "unidad", "poblacion", "muestra", "participantes"),
    },
    {
        "label": "Variables o categorias",
        "keywords": ("variable", "indicador", "factor", "efecto", "relacion", "dependiente", "independiente", "categoria"),
    },
    {
        "label": "Objetivo o resultado esperado",
        "keywords": ("objetivo", "determinar", "evaluar", "analizar", "disenar", "desarrollar", "mejorar", "proponer", "implementar"),
    },
    {
        "label": "Tipo, nivel o diseno preliminar",
        "keywords": ("basica", "aplicada", "exploratorio", "descriptivo", "correlacional", "explicativo", "predictivo", "aplicativo", "experimental", "transversal", "longitudinal"),
    },
    {
        "label": "Datos, instrumentos o tecnica",
        "keywords": ("datos", "encuesta", "entrevista", "medicion", "registros", "dataset", "metodo", "metodologia", "instrumento", "software", "estadistica", "anova", "regresion", "validacion", "simulacion", "prueba"),
    },
    {
        "label": "Justificacion, importancia o factibilidad",
        "keywords": ("justificacion", "importancia", "social", "economico", "cientifico", "factible", "recursos", "tiempo", "viable"),
    },
    {
        "label": "Antecedentes o referencias base",
        "keywords": ("antecedente", "articulo", "paper", "referencia", "autor", "scopus", "scielo", "ieee", "apa"),
    },
)

DEFAULT_THESIS_PLAN_PROBLEM_SUGGESTIONS = (
    {
        "id": "seguimiento-tesis-ia",
        "title": "Sistema inteligente para el seguimiento de planes de tesis universitarios",
        "problem": (
            "Los estudiantes y asesores universitarios suelen enfrentar demoras, baja trazabilidad "
            "y retroalimentacion dispersa durante la formulacion de planes de tesis, lo que afecta "
            "la calidad metodologica y la culminacion oportuna de los proyectos."
        ),
        "community_impact": (
            "Beneficia a estudiantes, docentes y coordinaciones academicas al mejorar el acompanamiento, "
            "reducir reprocesos y elevar la calidad de los trabajos de investigacion."
        ),
        "research_context": (
            "Facultades de ingenieria de universidades peruanas durante el periodo academico 2026-I."
        ),
        "variables": (
            "Sistema inteligente de seguimiento; calidad metodologica; tiempo de revision; "
            "satisfaccion del estudiante; trazabilidad de observaciones."
        ),
    },
    {
        "id": "alertas-salud-comunitaria",
        "title": "Aplicacion de alertas tempranas para riesgos de salud comunitaria",
        "problem": (
            "Los establecimientos y actores comunitarios tienen dificultades para detectar patrones "
            "tempranos de riesgo sanitario debido a registros fragmentados, comunicacion tardia y "
            "escasa visualizacion de incidencias locales."
        ),
        "community_impact": (
            "Ayuda a priorizar acciones preventivas, orientar campanas de salud y responder con mayor "
            "rapidez ante problemas que afectan a barrios, colegios y familias."
        ),
        "research_context": (
            "Centros de salud, municipalidades y organizaciones vecinales urbanas de Tacna."
        ),
        "variables": (
            "Sistema de alertas tempranas; oportunidad de respuesta; calidad del registro; "
            "percepcion de utilidad; indicadores de riesgo comunitario."
        ),
    },
    {
        "id": "gestion-residuos-ciudadana",
        "title": "Plataforma ciudadana para optimizar la gestion de residuos solidos",
        "problem": (
            "La gestion de residuos solidos presenta rutas poco optimizadas, reportes ciudadanos "
            "desordenados y limitada retroalimentacion sobre puntos criticos, generando acumulacion "
            "de residuos y baja confianza en el servicio municipal."
        ),
        "community_impact": (
            "Mejora la limpieza urbana, promueve participacion ciudadana y permite tomar decisiones "
            "basadas en datos para proteger el ambiente local."
        ),
        "research_context": (
            "Municipalidades distritales y juntas vecinales de zonas urbanas y periurbanas."
        ),
        "variables": (
            "Plataforma ciudadana; eficiencia de recoleccion; tiempo de atencion; participacion "
            "ciudadana; puntos criticos de acumulacion."
        ),
    },
    {
        "id": "seguridad-mujeres-rutas",
        "title": "Sistema de rutas seguras para movilidad de mujeres y estudiantes",
        "problem": (
            "Muchas personas evitan determinadas rutas por percepcion de inseguridad, falta de datos "
            "comunitarios y ausencia de recomendaciones contextualizadas para desplazarse hacia "
            "centros de estudio, trabajo o servicios publicos."
        ),
        "community_impact": (
            "Contribuye a la movilidad segura, la prevencion situacional y la toma de decisiones "
            "informada por parte de estudiantes, familias e instituciones."
        ),
        "research_context": (
            "Entornos universitarios, avenidas principales y rutas peatonales de alta circulacion."
        ),
        "variables": (
            "Sistema de rutas seguras; percepcion de seguridad; tiempo de desplazamiento; "
            "incidencias reportadas; usabilidad de la aplicacion."
        ),
    },
    {
        "id": "accesibilidad-servicios-publicos",
        "title": "Modelo digital para evaluar accesibilidad a servicios publicos locales",
        "problem": (
            "Los ciudadanos encuentran barreras para identificar servicios publicos cercanos, horarios, "
            "requisitos y condiciones de accesibilidad, especialmente cuando la informacion se encuentra "
            "dispersa o desactualizada."
        ),
        "community_impact": (
            "Reduce brechas de acceso, facilita la orientacion ciudadana y apoya decisiones municipales "
            "sobre mejora de servicios y atencion inclusiva."
        ),
        "research_context": (
            "Servicios municipales, educativos, sanitarios y administrativos de gobiernos locales."
        ),
        "variables": (
            "Modelo digital de accesibilidad; disponibilidad de informacion; tiempo de busqueda; "
            "satisfaccion ciudadana; cumplimiento de criterios de accesibilidad."
        ),
    },
)

DEFAULT_EMBEDDING_DIM = 3072
DEFAULT_EMBEDDING_MODEL_FALLBACKS = (
    "text-embedding-005",
    "models/text-embedding-005",
    "text-embedding-004",
    "models/text-embedding-004",
    "gemini-embedding-001",
    "models/gemini-embedding-001",
    "models/embedding-001",
    "embedding-001",
)
DEFAULT_CHAT_MODEL_FALLBACKS = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
)
AI_PROVIDER_GEMINI = "gemini"
AI_PROVIDER_DEEPSEEK = "deepseek"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
TOKEN_PATTERN = re.compile(r"[\w\-]+", re.UNICODE)
RETRY_IN_SECONDS_PATTERN = re.compile(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
RETRY_DELAY_SECONDS_PATTERN = re.compile(r"retrydelay\s*'?:\s*'([0-9]+)s'", re.IGNORECASE)
MIN_STRUCTURED_REVIEW_CHARS = 900
LOGGER = logging.getLogger(__name__)


class GeminiServiceError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class GeminiService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: genai.Client | None = None
        self._discovered_generation_models: list[str] | None = None
        self._discovered_embedding_models: list[str] | None = None
        self._disable_remote_embeddings = False
        self._embedding_fallback_warned = False
        self._disable_remote_generation = False
        self._generation_retry_after_epoch = 0.0
        self._generation_unavailable_reason = ""
        self._generation_fallback_warned = False

    @staticmethod
    def _extract_retry_after_seconds(error_message: str) -> float | None:
        message = (error_message or "").strip()
        if not message:
            return None

        retry_in_match = RETRY_IN_SECONDS_PATTERN.search(message)
        if retry_in_match:
            try:
                return max(float(retry_in_match.group(1)), 0.0)
            except ValueError:
                pass

        retry_delay_match = RETRY_DELAY_SECONDS_PATTERN.search(message)
        if retry_delay_match:
            try:
                return max(float(retry_delay_match.group(1)), 0.0)
            except ValueError:
                pass

        return None

    def _clear_generation_unavailable(self) -> None:
        self._disable_remote_generation = False
        self._generation_retry_after_epoch = 0.0
        self._generation_unavailable_reason = ""
        self._generation_fallback_warned = False

    def _mark_generation_unavailable(
        self,
        reason: str,
        *,
        disable_remote: bool,
        retry_after_seconds: float | None = None,
    ) -> None:
        self._generation_unavailable_reason = (reason or "").strip()
        self._disable_remote_generation = disable_remote

        if retry_after_seconds and retry_after_seconds > 0:
            next_retry_epoch = time.time() + retry_after_seconds
            self._generation_retry_after_epoch = max(
                self._generation_retry_after_epoch,
                next_retry_epoch,
            )

    def _register_generation_failure(self, error_message: str) -> None:
        lower_message = (error_message or "").lower()
        retry_after_seconds = self._extract_retry_after_seconds(error_message)

        if "resource_exhausted" in lower_message or "quota exceeded" in lower_message:
            self._mark_generation_unavailable(
                "Gemini no disponible por cuota agotada (429).",
                disable_remote=True,
                retry_after_seconds=retry_after_seconds,
            )
            return

        if "unavailable" in lower_message and "high demand" in lower_message:
            self._mark_generation_unavailable(
                "Gemini no disponible temporalmente por alta demanda (503).",
                disable_remote=False,
                retry_after_seconds=retry_after_seconds or 60,
            )
            return

        if "not_found" in lower_message or "not found" in lower_message:
            self._mark_generation_unavailable(
                "Modelo Gemini no disponible para la API/configuracion actual.",
                disable_remote=False,
                retry_after_seconds=retry_after_seconds or 300,
            )

    def _should_skip_remote_generation(self) -> bool:
        if self._disable_remote_generation:
            return True

        if self._generation_retry_after_epoch <= 0:
            return False

        if time.time() < self._generation_retry_after_epoch:
            return True

        self._clear_generation_unavailable()
        return False

    def _get_generation_unavailability_reason(self) -> str | None:
        reason = self._generation_unavailable_reason.strip()
        return reason or None

    @staticmethod
    def _extract_embedding(payload: object) -> list[float] | None:
        if isinstance(payload, dict):
            embeddings = payload.get("embeddings")
            if isinstance(embeddings, list) and embeddings:
                first_embedding = embeddings[0]
                if isinstance(first_embedding, dict):
                    values = first_embedding.get("values")
                    if isinstance(values, list):
                        return [float(value) for value in values]
                values_attr = getattr(first_embedding, "values", None)
                if isinstance(values_attr, list):
                    return [float(value) for value in values_attr]

            embedding = payload.get("embedding")
            if isinstance(embedding, list):
                return [float(value) for value in embedding]
            if isinstance(embedding, dict):
                values = embedding.get("values")
                if isinstance(values, list):
                    return [float(value) for value in values]

        embedding_attr = getattr(payload, "embedding", None)
        if isinstance(embedding_attr, list):
            return [float(value) for value in embedding_attr]

        values_attr = getattr(embedding_attr, "values", None)
        if isinstance(values_attr, list):
            return [float(value) for value in values_attr]

        embeddings_attr = getattr(payload, "embeddings", None)
        if isinstance(embeddings_attr, list) and embeddings_attr:
            first_embedding = embeddings_attr[0]
            values_attr = getattr(first_embedding, "values", None)
            if isinstance(values_attr, list):
                return [float(value) for value in values_attr]

        return None

    @staticmethod
    def _model_aliases(model_name: str) -> list[str]:
        clean_name = (model_name or "").strip()
        if not clean_name:
            return []

        aliases = [clean_name]
        if clean_name.startswith("models/"):
            aliases.append(clean_name[len("models/") :])
        else:
            aliases.append(f"models/{clean_name}")

        seen: set[str] = set()
        ordered: list[str] = []
        for alias in aliases:
            if alias not in seen:
                seen.add(alias)
                ordered.append(alias)
        return ordered

    @staticmethod
    def _dedupe_models(models: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for model_name in models:
            for alias in GeminiService._model_aliases(model_name):
                if alias not in seen:
                    seen.add(alias)
                    ordered.append(alias)
        return ordered

    def _discover_models_for_method(self, method: str) -> list[str]:
        client = self._get_client()

        try:
            discovered = list(client.models.list())
        except Exception as error:  # pragma: no cover - llamada externa
            LOGGER.warning("No se pudieron listar modelos de Gemini: %s", error)
            return []

        model_names: list[str] = []
        for model in discovered:
            methods = getattr(model, "supported_generation_methods", None) or []
            if method in methods:
                name = getattr(model, "name", "")
                if name:
                    model_names.append(name)

        return self._dedupe_models(model_names)

    def _candidate_embedding_models(self) -> list[str]:
        candidates: list[str] = []
        configured = (self.settings.gemini_embedding_model or "").strip()
        if configured:
            candidates.extend(self._model_aliases(configured))

        for fallback_model in DEFAULT_EMBEDDING_MODEL_FALLBACKS:
            candidates.extend(self._model_aliases(fallback_model))

        if self._discovered_embedding_models is None:
            self._discovered_embedding_models = self._discover_models_for_method(
                "embedContent"
            )

        candidates.extend(self._discovered_embedding_models)

        return self._dedupe_models(candidates)

    def _candidate_chat_models(self, model_override: str | None = None) -> list[str]:
        candidates: list[str] = []
        configured = (model_override or self.settings.gemini_chat_model or "").strip()
        if configured:
            candidates.extend(self._model_aliases(configured))

        for fallback_model in DEFAULT_CHAT_MODEL_FALLBACKS:
            candidates.extend(self._model_aliases(fallback_model))

        if self._discovered_generation_models is None:
            self._discovered_generation_models = self._discover_models_for_method(
                "generateContent"
            )

        candidates.extend(self._discovered_generation_models)

        return self._dedupe_models(candidates)

    @staticmethod
    def _local_embedding(content: str, dimensions: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
        vector = [0.0] * dimensions
        tokens = TOKEN_PATTERN.findall(content.lower())

        if not tokens:
            tokens = [content.lower().strip() or "vacio"]

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if (digest[4] % 2 == 0) else -1.0
            weight = 1.0 + (digest[5] / 255.0) * 0.2
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            return vector

        return [value / norm for value in vector]

    def _coerce_embedding_dimension(self, embedding: list[float]) -> list[float]:
        target_dimension = self.settings.gemini_embedding_output_dimensionality
        if target_dimension <= 0:
            target_dimension = DEFAULT_EMBEDDING_DIM

        if len(embedding) == target_dimension:
            return embedding

        if len(embedding) > target_dimension:
            return embedding[:target_dimension]

        return embedding + [0.0] * (target_dimension - len(embedding))

    def _get_client(self) -> genai.Client:
        self._ensure_ready()
        if self._client is None:
            raise GeminiServiceError("No se pudo inicializar el cliente de Gemini.")
        return self._client

    def _embed_with_gemini(self, content: str, task_type: str) -> list[float]:
        client = self._get_client()
        errors: list[str] = []

        for model_name in self._candidate_embedding_models():
            try:
                response = client.models.embed_content(
                    model=model_name,
                    contents=content,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.settings.gemini_embedding_output_dimensionality,
                    ),
                )
            except Exception as error:  # pragma: no cover - llamada externa
                errors.append(f"{model_name}: {error}")
                continue

            embedding = self._extract_embedding(response)
            if embedding:
                return embedding

            errors.append(f"{model_name}: embedding vacio")

        errors_preview = "; ".join(errors[:2]) if errors else "sin detalles"
        raise GeminiServiceError(
            "No se pudieron generar embeddings con Gemini. "
            f"Detalles: {errors_preview}"
        )

    def _embed_text_with_fallback(self, content: str, task_type: str) -> list[float]:
        if self._disable_remote_embeddings:
            embedding = self._local_embedding(
                content,
                dimensions=self.settings.gemini_embedding_output_dimensionality,
            )
            return self._coerce_embedding_dimension(embedding)

        try:
            embedding = self._embed_with_gemini(content=content, task_type=task_type)
        except GeminiServiceError as error:
            error_message = (error.message or "").lower()
            is_unavailable_model = (
                "not found" in error_message
                or "not supported for embedcontent" in error_message
                or "unsupported for embedcontent" in error_message
            )

            if is_unavailable_model:
                self._disable_remote_embeddings = True

            if not self._embedding_fallback_warned:
                LOGGER.warning(
                    "Fallo embedding con Gemini, usando fallback local: %s",
                    error.message,
                )
                if self._disable_remote_embeddings:
                    LOGGER.warning(
                        "Se desactivan intentos de embedding remoto para evitar errores repetidos."
                    )
                self._embedding_fallback_warned = True

            embedding = self._local_embedding(
                content,
                dimensions=self.settings.gemini_embedding_output_dimensionality,
            )

        return self._coerce_embedding_dimension(embedding)

    def _ensure_ready(self) -> None:
        if self._client is not None:
            return

        if not self.settings.gemini_api_key:
            raise GeminiServiceError(
                "GEMINI_API_KEY (o API_GEMINI) no esta configurado en el backend."
            )

        api_version = (self.settings.gemini_api_version or "").strip()
        if api_version:
            self._client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options={"api_version": api_version},
            )
        else:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)

    def embed_documents(self, chunks: list[str]) -> list[list[float]]:
        return [
            self._embed_text_with_fallback(chunk, task_type="RETRIEVAL_DOCUMENT")
            for chunk in chunks
        ]

    def embed_query(self, question: str) -> list[float]:
        return self._embed_text_with_fallback(
            question,
            task_type="RETRIEVAL_QUERY",
        )

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return "Sin historial previo."

        lines: list[str] = []
        for message in history[-10:]:
            role = message.get("role", "user")
            content = GeminiService._truncate_text(
                str(message.get("content", "")),
                max_chars=900,
            )
            if not content:
                continue
            lines.append(f"{role.upper()}: {content}")

        return "\n".join(lines) if lines else "Sin historial previo."

    @staticmethod
    def _format_context(context_chunks: list[dict]) -> str:
        if not context_chunks:
            return "No se recuperaron fragmentos relevantes del documento."

        lines: list[str] = []
        for index, chunk in enumerate(context_chunks, start=1):
            content = (chunk.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"[Fragmento {index}] {content}")

        return "\n\n".join(lines) if lines else "No se recuperaron fragmentos relevantes."

    def _build_prompt(
        self,
        question: str,
        context_chunks: list[dict],
        history: list[dict],
    ) -> str:
        context_block = self._format_context(context_chunks)
        history_block = self._format_history(history)

        return (
            "Contexto recuperado de la tesis:\n"
            f"{context_block}\n\n"
            "Historial de la conversacion:\n"
            f"{history_block}\n\n"
            "Pregunta del estudiante:\n"
            f"{question}\n\n"
            "Instruccion de estilo:\n"
            "- No inicies con saludo ni presentacion personal.\n\n"
            "Responde en formato:\n"
            "- Diagnostico breve\n"
            "- Hallazgos especificos\n"
            "- Recomendaciones accionables\n\n"
            "Profundidad minima esperada:\n"
            "- Entrega una respuesta completa, no una frase corta.\n"
            "- Incluye al menos 6 hallazgos puntuales cuando haya evidencia suficiente."
        )

    @staticmethod
    def _normalize_ai_provider(provider: str | None) -> str:
        normalized = (provider or AI_PROVIDER_GEMINI).strip().lower()
        if normalized == AI_PROVIDER_DEEPSEEK:
            return AI_PROVIDER_DEEPSEEK
        return AI_PROVIDER_GEMINI

    def _resolve_generation_model(self, provider: str, model: str | None = None) -> str:
        clean_model = (model or "").strip()
        if clean_model:
            return clean_model[:120]

        if provider == AI_PROVIDER_DEEPSEEK:
            return (self.settings.deepseek_chat_model or DEFAULT_DEEPSEEK_MODEL).strip()

        return (self.settings.gemini_chat_model or "gemini-2.0-flash").strip()

    @staticmethod
    def _deepseek_base_url(base_url: str) -> str:
        clean_base_url = (base_url or "https://api.deepseek.com").strip().rstrip("/")
        return clean_base_url or "https://api.deepseek.com"

    @staticmethod
    def _extract_text_from_openai_compatible_response(payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        text = first_choice.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

        return ""

    @staticmethod
    def _prompt_with_system_instruction(prompt: str, system_instruction: str) -> str:
        instruction = (system_instruction or "").strip()
        content = (prompt or "").strip()
        if not instruction:
            return content
        return f"Instrucciones del sistema:\n{instruction}\n\nSolicitud:\n{content}"

    def _generate_with_deepseek(
        self,
        prompt: str,
        system_instruction: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> str:
        if not self.settings.deepseek_api_key:
            raise GeminiServiceError("DEEPSEEK_API_KEY no esta configurado en el backend.")

        selected_model = self._resolve_generation_model(AI_PROVIDER_DEEPSEEK, model)
        max_tokens = max(
            int(max_output_tokens or self.settings.deepseek_chat_max_output_tokens),
            1024,
        )
        endpoint = f"{self._deepseek_base_url(self.settings.deepseek_base_url)}/chat/completions"
        base_payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        payloads = [base_payload]
        if selected_model.startswith("deepseek-v4"):
            thinking_payload = {
                **base_payload,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
            payloads = [thinking_payload, base_payload]

        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        errors: list[str] = []

        for payload in payloads:
            try:
                response = httpx.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=90.0,
                )
            except Exception as error:
                errors.append(str(error))
                continue

            if response.status_code >= 400:
                errors.append(f"{response.status_code}: {response.text[:300]}")
                continue

            try:
                response_payload = response.json()
            except ValueError:
                errors.append("respuesta no JSON")
                continue

            text = self._extract_text_from_openai_compatible_response(response_payload)
            if text:
                return text

            errors.append("respuesta sin contenido")

        errors_preview = "; ".join(errors[:2]) if errors else "sin detalles"
        raise GeminiServiceError(
            f"No se pudo generar respuesta con DeepSeek ({selected_model}). Detalles: {errors_preview}"
        )

    def _generate_with_gemini(
        self,
        prompt: str,
        system_instruction: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> str:
        if self._should_skip_remote_generation():
            raise GeminiServiceError(
                self._get_generation_unavailability_reason()
                or "Gemini no disponible temporalmente."
            )

        try:
            self._ensure_ready()
        except GeminiServiceError as error:
            self._mark_generation_unavailable(
                "Gemini no configurado o credenciales invalidas.",
                disable_remote=True,
            )
            raise error

        client = self._get_client()
        model_errors: list[str] = []

        for model_name in self._candidate_chat_models(model):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=self._prompt_with_system_instruction(prompt, system_instruction),
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max(
                            int(max_output_tokens or self.settings.gemini_review_max_output_tokens),
                            1024,
                        ),
                    ),
                )
            except Exception as error:  # pragma: no cover - llamada externa
                model_errors.append(f"{model_name}: {error}")
                self._register_generation_failure(str(error))
                continue

            text = self._extract_text_from_generation_response(response)
            if text:
                self._clear_generation_unavailable()
                return text

            model_errors.append(f"{model_name}: sin texto util")

        errors_preview = "; ".join(model_errors[:3]) if model_errors else "sin detalles"
        raise GeminiServiceError(f"No se pudo generar respuesta con Gemini. Detalles: {errors_preview}")

    def _generate_text(
        self,
        prompt: str,
        system_instruction: str,
        *,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> str:
        provider = self._normalize_ai_provider(ai_provider)
        if provider == AI_PROVIDER_DEEPSEEK:
            return self._generate_with_deepseek(
                prompt,
                system_instruction,
                model=ai_model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        return self._generate_with_gemini(
            prompt,
            system_instruction,
            model=ai_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    @staticmethod
    def _build_thesis_plan_system_instruction(academic_profile: dict | None = None) -> str:
        return (
            f"{THESIS_PLAN_SYSTEM_PROMPT}\n\n"
            "Contexto academico obligatorio:\n"
            f"{format_academic_context(academic_profile)}\n\n"
            "Reglas de adaptacion por carrera:\n"
            "- No fuerces entregables tecnologicos en carreras donde el producto esperado es evidencia, diagnostico, propuesta, protocolo, programa, modelo, diseno o plan.\n"
            "- Si la normativa de la facultad no exige hipotesis u operacionalizacion como seccion independiente, integrala solo cuando el enfoque metodologico lo justifique.\n"
            "- Los problemas sugeridos deben tener impacto social, institucional, productivo, clinico, educativo, urbano o economico en Tacna, Peru o a nivel nacional.\n"
            "- Mantiene independencia del proveedor: la misma instruccion debe funcionar con Gemini o DeepSeek sin depender de rasgos del modelo."
        )

    @staticmethod
    def _build_thesis_system_instruction(academic_profile: dict | None = None) -> str:
        return (
            f"{THESIS_SYSTEM_PROMPT}\n\n"
            "Contexto academico obligatorio:\n"
            f"{format_academic_context(academic_profile)}\n\n"
            "Reglas de adaptacion por carrera:\n"
            "- Respeta si el entregable esperado es software, prototipo, diseno arquitectonico, evidencia clinica, analisis econometrico, diagnostico empresarial, programa educativo, estudio psicologico o estrategia comunicacional.\n"
            "- No conviertas todas las tesis en proyectos de ingenieria de sistemas. Usa el lenguaje, datos, instrumentos y resultados propios de la carrera.\n"
            "- Si la carrera usa propuesta proyectual o tecnica, desarrolla memoria, criterios, componentes, validacion e indicadores. Si usa investigacion empirica, desarrolla analisis sin inventar datos reales.\n"
            "- Los problemas, recomendaciones y aportes deben mantener impacto social, institucional, productivo, clinico, educativo, urbano o economico en Tacna, Peru o alcance nacional."
        )

    @staticmethod
    def _build_academic_search_query(history: list[dict]) -> str:
        latest = GeminiService._extract_primary_user_plan_idea(history)
        if not latest:
            return ""

        tokens = [
            token
            for token in TOKEN_PATTERN.findall(GeminiService._normalize_for_matching(latest))
            if len(token) >= 4
        ]
        stopwords = {
            "para", "como", "sobre", "tesis", "plan", "quiero", "hacer", "desarrollar",
            "sistema", "software", "aplicacion", "proyecto", "mejorar", "mediante",
            "este", "esta", "estos", "estas", "tiene", "tengo", "usuario", "usuarios",
        }
        keywords = [token for token in tokens if token not in stopwords]
        if keywords:
            return " ".join(keywords[:10])
        return latest[:220]

    @staticmethod
    def _format_crossref_authors(authors: list[dict] | None) -> str:
        if not isinstance(authors, list) or not authors:
            return "Autor no identificado"

        formatted: list[str] = []
        for author in authors[:3]:
            family = (author.get("family") or "").strip()
            given = (author.get("given") or "").strip()
            if family and given:
                formatted.append(f"{family}, {given[:1]}.")
            elif family:
                formatted.append(family)

        if not formatted:
            return "Autor no identificado"
        if len(authors) > 3:
            formatted.append("et al.")
        return ", ".join(formatted)

    @staticmethod
    def _extract_crossref_year(item: dict) -> str:
        issued = item.get("issued") or {}
        date_parts = issued.get("date-parts") if isinstance(issued, dict) else None
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            year = date_parts[0][0] if date_parts[0] else None
            if year:
                return str(year)
        return "s. f."

    def _discover_academic_sources(
        self,
        history: list[dict],
        limit: int = 5,
        academic_profile: dict | None = None,
    ) -> list[str]:
        query = self._build_academic_search_query(history)
        profile_queries = []
        if academic_profile:
            profile_queries = list(academic_profile.get("search_terms") or [])
            career_name = str(academic_profile.get("name") or "").strip()
            thesis_focus = str(academic_profile.get("thesis_focus") or "").strip()
            if career_name:
                profile_queries.append(career_name)
            if thesis_focus:
                profile_queries.append(thesis_focus[:160])

        queries = [query, *profile_queries]
        clean_queries = []
        for candidate in queries:
            clean_candidate = (candidate or "").strip()
            if len(clean_candidate) >= 8 and clean_candidate not in clean_queries:
                clean_queries.append(clean_candidate)

        if not clean_queries:
            return []

        sources: list[str] = []
        seen_dois: set[str] = set()
        rows_per_query = max(min(limit, 20), 8)

        for clean_query in clean_queries:
            try:
                response = httpx.get(
                    "https://api.crossref.org/works",
                    params={
                        "query.bibliographic": clean_query,
                        "filter": "from-pub-date:2015-01-01",
                        "rows": rows_per_query,
                        "select": "title,DOI,URL,issued,container-title,author",
                        "sort": "relevance",
                    },
                    headers={"User-Agent": "tesis-ai-advisor/0.1 (mailto:dev@example.com)"},
                    timeout=14.0,
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
            except Exception:
                continue

            items = (((payload or {}).get("message") or {}).get("items") or [])[:rows_per_query]
            for item in items:
                titles = item.get("title") or []
                title = titles[0].strip() if titles and isinstance(titles[0], str) else ""
                doi = (item.get("DOI") or "").strip()
                normalized_doi = doi.lower()
                if not title or not doi or normalized_doi in seen_dois:
                    continue

                authors = self._format_crossref_authors(item.get("author"))
                year = self._extract_crossref_year(item)
                journal_values = item.get("container-title") or []
                journal = journal_values[0].strip() if journal_values and isinstance(journal_values[0], str) else ""
                source = f"{authors} ({year}). {title}."
                if journal:
                    source = f"{source} {journal}."
                source = f"{source} https://doi.org/{doi}"
                sources.append(source)
                seen_dois.add(normalized_doi)

                if len(sources) >= limit:
                    return sources

        return sources

    @staticmethod
    def _format_academic_sources(sources: list[str]) -> str:
        if not sources:
            return "- No se encontraron referencias candidatas automaticamente."
        return "\n".join(f"- {source}" for source in sources)

    @staticmethod
    def _extract_latest_user_plan_idea(history: list[dict]) -> str:
        user_messages = [
            str(message.get("content", "")).strip()
            for message in history
            if (message.get("role") or "user") == "user" and str(message.get("content", "")).strip()
        ]
        return user_messages[-1] if user_messages else ""

    @staticmethod
    def _extract_primary_user_plan_idea(history: list[dict]) -> str:
        user_messages = [
            str(message.get("content", "")).strip()
            for message in history
            if (message.get("role") or "user") == "user" and str(message.get("content", "")).strip()
        ]
        if not user_messages:
            return ""

        for message in user_messages:
            normalized = GeminiService._normalize_for_matching(message)
            looks_like_question_answers = (
                re.search(r"\brespuesta\s*:", normalized) is not None
                and re.search(r"(^|\n)\s*\d+\.", message) is not None
            )
            if not looks_like_question_answers:
                return message

        return user_messages[0]

    @staticmethod
    def _build_plan_topic_seed(latest_idea: str) -> str:
        clean = " ".join((latest_idea or "").strip().split())
        if not clean:
            return "tema de investigacion por definir"

        clean = re.sub(
            r"^concepto\s+general\s+del\s+sistema\s*[:.-]?\s*",
            "",
            clean,
            flags=re.IGNORECASE,
        )
        project_match = re.search(
            r"(?:tu\s+proyecto\s+es|el\s+proyecto\s+es|la\s+propuesta\s+es)\s+"
            r"(?:un|una)?\s*(.+?)(?:\.\s|;\s|,\s+nace|\s+para\s+resolver)",
            clean,
            flags=re.IGNORECASE,
        )
        if project_match:
            clean = project_match.group(1).strip()

        clean = re.sub(
            r"^(quiero|deseo|busco|necesito)\s+"
            r"(hacer|investigar|desarrollar|crear|proponer|elaborar)\s+",
            "",
            clean,
            flags=re.IGNORECASE,
        )
        clean = clean.strip(" .,:;")
        words = clean.split()
        if len(words) > 11:
            clean = " ".join(words[:11])

        return clean or "tema de investigacion por definir"

    @staticmethod
    def _build_tentative_plan_elements(
        latest_idea: str,
        academic_profile: dict | None = None,
    ) -> dict[str, str]:
        topic_seed = GeminiService._build_plan_topic_seed(latest_idea)
        search_seed = GeminiService._truncate_text(topic_seed, max_chars=80)
        idea_summary = GeminiService._truncate_text(
            latest_idea or "Aun no hay una descripcion suficiente de la idea.",
            max_chars=900,
        )
        career_name = (
            str((academic_profile or {}).get("name") or "").strip()
            or "la carrera seleccionada"
        )
        data_sources = (
            str((academic_profile or {}).get("data_sources") or "").strip()
            or "encuestas, entrevistas, revision documental, mediciones o registros disponibles"
        )
        deliverable = (
            str((academic_profile or {}).get("deliverable") or "").strip()
            or "una propuesta metodologicamente viable y sustentada con evidencia"
        )
        variables_hint = (
            str((academic_profile or {}).get("variables_hint") or "").strip()
            or "Variable/categoria central: tema declarado por el estudiante; resultado esperado: mejora o evidencia medible."
        )
        return {
            "idea_summary": idea_summary,
            "title_1": f"{topic_seed}: analisis y propuesta desde {career_name}",
            "title_2": f"{topic_seed} en contextos de Tacna, 2026",
            "problem": (
                f"¿Como se manifiesta el problema asociado a {topic_seed} "
                f"en el campo de {career_name} en Tacna?"
            ),
            "objective": (
                f"Analizar el problema asociado a {topic_seed} y formular {deliverable}."
            ),
            "variables": variables_hint,
            "unit": f"Unidad, datos o evidencia tentativa: {data_sources}.",
            "search_terms": (
                f"{search_seed} investigacion aplicada; {search_seed} variables; "
                f"{search_seed} antecedentes cientificos; {search_seed} metodologia"
            ),
        }

    @staticmethod
    def thesis_plan_manual_sections(academic_profile: dict | None = None) -> list[str]:
        if academic_profile and academic_profile.get("plan_sections"):
            return list(academic_profile.get("plan_sections") or [])
        return list(THESIS_PLAN_MANUAL_SECTIONS)

    @staticmethod
    def thesis_plan_complete_sections() -> list[dict[str, str | int]]:
        total = len(THESIS_PLAN_COMPLETE_SECTIONS)
        return [
            {
                "id": str(section["id"]),
                "title": str(section["title"]),
                "index": index,
                "total": total,
            }
            for index, section in enumerate(THESIS_PLAN_COMPLETE_SECTIONS, start=1)
        ]

    @staticmethod
    def _fallback_thesis_plan_problem_suggestions(
        academic_profile: dict | None = None,
    ) -> list[dict[str, str]]:
        profile_suggestions = build_fallback_problem_suggestions(academic_profile)
        if profile_suggestions:
            return profile_suggestions
        return [dict(item) for item in DEFAULT_THESIS_PLAN_PROBLEM_SUGGESTIONS]

    @staticmethod
    def _sanitize_problem_suggestion(raw_item: dict, fallback_id: str) -> dict[str, str] | None:
        if not isinstance(raw_item, dict):
            return None

        title = " ".join(str(raw_item.get("title") or "").split())[:180]
        problem = " ".join(str(raw_item.get("problem") or "").split())[:1200]
        community_impact = " ".join(
            str(raw_item.get("community_impact") or raw_item.get("impact") or "").split()
        )[:700]
        research_context = " ".join(
            str(raw_item.get("research_context") or raw_item.get("context") or "").split()
        )[:700]
        variables = " ".join(str(raw_item.get("variables") or "").split())[:700]
        item_id = " ".join(str(raw_item.get("id") or fallback_id).split())[:80]

        if len(title) < 5 or len(problem) < 20:
            return None

        if len(community_impact) < 10:
            community_impact = "Aporta valor social mediante una propuesta o evidencia viable y evaluable."
        if len(research_context) < 10:
            research_context = "Comunidad local, instituciones publicas o entornos universitarios de Tacna."
        if len(variables) < 10:
            variables = "Factor principal; resultado esperado; satisfaccion; calidad de servicio; indicadores de mejora."

        return {
            "id": item_id,
            "title": title,
            "problem": problem,
            "community_impact": community_impact,
            "research_context": research_context,
            "variables": variables,
        }

    @classmethod
    def _parse_problem_suggestions(cls, text: str) -> list[dict[str, str]]:
        clean_text = (text or "").strip()
        if not clean_text:
            return []

        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\s*```$", "", clean_text)

        payload = None
        try:
            payload = json.loads(clean_text)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", clean_text)
            if match:
                try:
                    payload = json.loads(match.group(0))
                except json.JSONDecodeError:
                    payload = None

        if isinstance(payload, dict):
            payload = payload.get("suggestions") or payload.get("problemas") or []

        if not isinstance(payload, list):
            return []

        suggestions: list[dict[str, str]] = []
        seen_titles: set[str] = set()
        for index, item in enumerate(payload, start=1):
            suggestion = cls._sanitize_problem_suggestion(item, fallback_id=f"problema-{index}")
            if not suggestion:
                continue

            normalized_title = cls._normalize_for_matching(suggestion["title"])
            if normalized_title in seen_titles:
                continue

            suggestions.append(suggestion)
            seen_titles.add(normalized_title)
            if len(suggestions) >= 5:
                break

        return suggestions

    def generate_thesis_plan_problem_suggestions(
        self,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        academic_profile: dict | None = None,
    ) -> list[dict[str, str]]:
        context = build_problem_suggestion_context(academic_profile)
        prompt = (
            "Propone exactamente 5 problemas de investigacion para planes de tesis segun "
            "la facultad y carrera seleccionadas.\n"
            "Deben ser viables para estudiantes universitarios, investigables en 2026, con datos "
            "recolectables mediante tecnicas coherentes con la carrera. Evita temas genericos, "
            "evita pedir informacion al usuario y prioriza problemas sociales, institucionales, "
            "productivos, clinicos, educativos, urbanos o economicos de Tacna, Peru o alcance nacional.\n\n"
            "Contexto obligatorio de carrera:\n"
            f"{context}\n\n"
            "Devuelve solo JSON valido, sin markdown, con este formato exacto:\n"
            "[\n"
            "  {\n"
            '    "id": "slug-corto",\n'
            '    "title": "titulo academico del problema",\n'
            '    "problem": "descripcion del problema observable",\n'
            '    "community_impact": "beneficio para la comunidad",\n'
            '    "research_context": "contexto, poblacion o unidad de analisis sugerida",\n'
            '    "variables": "variables, categorias o indicadores tentativos"\n'
            "  }\n"
            "]"
        )
        provider = self._normalize_ai_provider(ai_provider)

        if provider == AI_PROVIDER_GEMINI and self._should_skip_remote_generation():
            return self._fallback_thesis_plan_problem_suggestions(academic_profile)

        try:
            text = self._generate_text(
                prompt,
                self._build_thesis_plan_system_instruction(academic_profile),
                ai_provider=provider,
                ai_model=ai_model,
                temperature=0.55,
                max_output_tokens=2048,
            )
        except GeminiServiceError as error:
            if not self._generation_fallback_warned:
                LOGGER.warning(
                    "Proveedor IA no disponible para sugerir problemas de tesis, usando fallback local: %s",
                    error.message,
                )
                self._generation_fallback_warned = True
            return self._fallback_thesis_plan_problem_suggestions(academic_profile)

        suggestions = self._parse_problem_suggestions(text)
        if len(suggestions) >= 5:
            return suggestions[:5]

        fallback = self._fallback_thesis_plan_problem_suggestions(academic_profile)
        seen_titles = {
            self._normalize_for_matching(item["title"])
            for item in suggestions
        }
        for item in fallback:
            normalized_title = self._normalize_for_matching(item["title"])
            if normalized_title in seen_titles:
                continue
            suggestions.append(item)
            seen_titles.add(normalized_title)
            if len(suggestions) >= 5:
                break

        return suggestions[:5]

    @staticmethod
    def _get_complete_section(section_id: str) -> tuple[int, dict[str, str]]:
        clean_section_id = (section_id or "").strip()
        for index, section in enumerate(THESIS_PLAN_COMPLETE_SECTIONS, start=1):
            if section["id"] == clean_section_id:
                return index, section
        valid_ids = ", ".join(str(section["id"]) for section in THESIS_PLAN_COMPLETE_SECTIONS)
        raise GeminiServiceError(f"Seccion de plan completo no valida. Usa una de: {valid_ids}.")

    @staticmethod
    def _format_formal_data(formal_data: dict[str, str] | None) -> str:
        data = formal_data or {}
        authors = (data.get("authors") or "").strip()
        advisor = (data.get("advisor") or "").strip()
        area = (data.get("area") or "").strip()
        research_line = (
            (data.get("research_line") or "").strip()
        )
        return (
            f"- Autor(es): {authors}\n"
            f"- Asesor: {advisor}\n"
            f"- Area de investigacion: {area}\n"
            f"- Linea de investigacion: {research_line}"
        )

    @staticmethod
    def _build_complete_section_prompt(
        history: list[dict],
        section: dict[str, str],
        section_index: int,
        formal_data: dict[str, str] | None,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
    ) -> str:
        primary_idea = GeminiService._extract_primary_user_plan_idea(history)
        latest_idea = GeminiService._extract_latest_user_plan_idea(history)
        history_block = GeminiService._format_history(history)
        formal_data_block = GeminiService._format_formal_data(formal_data)
        sources_block = GeminiService._format_academic_sources(academic_sources or [])
        total_sections = len(THESIS_PLAN_COMPLETE_SECTIONS)
        academic_context = format_academic_context(academic_profile)
        manual_name = (
            str((academic_profile or {}).get("manual_name") or "").strip()
            or "normativa academica de la facultad seleccionada"
        )
        min_references = int((academic_profile or {}).get("minimum_references") or 15)

        return (
            "Genera una etapa del documento academico completo de plan de tesis.\n"
            f"Etapa actual: {section_index}/{total_sections} - {section['title']}\n\n"
            "Idea central original del proyecto:\n"
            f"{primary_idea or latest_idea or 'No registrada.'}\n\n"
            "Historial reciente y secciones ya generadas:\n"
            f"{history_block}\n\n"
            "Datos formales disponibles para reemplazar placeholders:\n"
            f"{formal_data_block}\n\n"
            "Contexto academico obligatorio:\n"
            f"{academic_context}\n\n"
            "Referencias candidatas encontradas automaticamente:\n"
            f"{sources_block}\n\n"
            "Referencias base que puedes usar si son pertinentes:\n"
            f"- Universidad Privada de Tacna. {manual_name}.\n"
            "- Congreso de la Republica del Peru. (2011). Ley N. 29733, Ley de Proteccion de Datos Personales.\n"
            "- Normativa nacional peruana, normas tecnicas o guias profesionales pertinentes a la carrera.\n\n"
            "Objetivo especifico de esta etapa:\n"
            f"{section['focus']}\n\n"
            "Salida obligatoria de esta etapa:\n"
            f"{section['required_output']}\n\n"
            "Reglas de calidad academica:\n"
            "- Redacta con estilo formal de plan de tesis, no como chat ni como checklist de tareas.\n"
            "- No uses placeholders como [Nombre del estudiante] o [Nombre del asesor].\n"
            "- Esta etapa se genera despues de que el estudiante respondio los datos requeridos; no escribas 'por validar', 'por completar', 'pendiente de confirmar' ni expresiones equivalentes.\n"
            "- No dejes secciones en blanco ni escribas 'referencias por completar'.\n"
            f"- Si estas en la etapa de referencias, entrega al menos {min_references} referencias verificables cuando existan fuentes suficientes; prioriza DOI en formato https://doi.org/...\n"
            "- No inventes autores, DOI, resultados empiricos ni datos institucionales no proporcionados.\n"
            "- No cites resultados empiricos puntuales de una referencia si no estan explicitamente en la referencia candidata; puedes usarla como soporte tematico general.\n"
            "- Mantiene coherencia con el enfoque, fuentes de datos, entregable y variables/categorias frecuentes de la carrera seleccionada.\n"
            "- Si la facultad no exige una seccion de hipotesis u operacionalizacion independiente, adapta el contenido como categorias, criterios de diseno, dimensiones, indicadores o supuestos metodologicos segun corresponda.\n"
            "- Usa tablas Markdown cuando la seccion lo requiera.\n"
            "- Entrega solo el contenido de la etapa solicitada, empezando con el titulo exacto de la etapa."
        )

    @staticmethod
    def _build_local_complete_section(
        history: list[dict],
        section: dict[str, str],
        section_index: int,
        formal_data: dict[str, str] | None = None,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
        unavailable_reason: str | None = None,
    ) -> str:
        tentative = GeminiService._build_tentative_plan_elements(
            GeminiService._extract_primary_user_plan_idea(history)
            or GeminiService._extract_latest_user_plan_idea(history),
            academic_profile=academic_profile,
        )
        formal_data_block = GeminiService._format_formal_data(formal_data)
        sources_block = GeminiService._format_academic_sources(academic_sources or [])
        academic_context = format_academic_context(academic_profile)
        warning = (
            f"\n\nNota tecnica: se uso una plantilla local porque el proveedor IA no completo la etapa. Detalle: {unavailable_reason}"
            if unavailable_reason
            else ""
        )
        return (
            f"{section['title']}\n\n"
            f"Esta etapa debe desarrollarse sobre el proyecto: {tentative['title_1']}.\n\n"
            "Datos formales registrados:\n"
            f"{formal_data_block}\n\n"
            "Contexto academico:\n"
            f"{academic_context}\n\n"
            "Contenido minimo esperado:\n"
            f"{section['required_output']}\n\n"
            "Elementos metodologicos base:\n"
            f"- Problema general tentativo: {tentative['problem']}.\n"
            f"- Objetivo general tentativo: {tentative['objective']}.\n"
            f"- Variables/categorias tentativas: {tentative['variables']}\n"
            f"- Unidad y datos tentativos: {tentative['unit']}\n\n"
            "Referencias candidatas:\n"
            f"{sources_block}"
            f"{warning}"
        )

    def generate_thesis_plan_complete_section(
        self,
        history: list[dict] | None,
        section_id: str,
        formal_data: dict[str, str] | None = None,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        academic_profile: dict | None = None,
    ) -> tuple[str, int, str, int]:
        conversation_history = history or []
        section_index, section = self._get_complete_section(section_id)
        source_limit = 18 if section_id == "administrativos_referencias" else 8
        academic_sources = self._discover_academic_sources(
            conversation_history,
            limit=source_limit,
            academic_profile=academic_profile,
        )
        prompt = self._build_complete_section_prompt(
            history=conversation_history,
            section=section,
            section_index=section_index,
            formal_data=formal_data,
            academic_sources=academic_sources,
            academic_profile=academic_profile,
        )

        provider = self._normalize_ai_provider(ai_provider)
        try:
            text = self._generate_text(
                prompt,
                self._build_thesis_plan_system_instruction(academic_profile),
                ai_provider=provider,
                ai_model=ai_model,
                temperature=0.2,
                max_output_tokens=max(
                    int(
                        self.settings.deepseek_chat_max_output_tokens
                        if provider == AI_PROVIDER_DEEPSEEK
                        else self.settings.gemini_review_max_output_tokens
                    ),
                    6144,
                ),
            )
        except GeminiServiceError as error:
            text = self._build_local_complete_section(
                history=conversation_history,
                section=section,
                section_index=section_index,
                formal_data=formal_data,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason=error.message,
            )

        clean_text = (text or "").strip()
        if len(clean_text) < 450:
            clean_text = self._build_local_complete_section(
                history=conversation_history,
                section=section,
                section_index=section_index,
                formal_data=formal_data,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason="respuesta insuficiente del proveedor IA",
            )

        return clean_text, section_index, str(section["title"]), len(THESIS_PLAN_COMPLETE_SECTIONS)

    @staticmethod
    def thesis_complete_sections() -> list[dict[str, str | int]]:
        total = len(THESIS_COMPLETE_SECTIONS)
        return [
            {
                "id": str(section["id"]),
                "title": str(section["title"]),
                "index": index,
                "total": total,
            }
            for index, section in enumerate(THESIS_COMPLETE_SECTIONS, start=1)
        ]

    @staticmethod
    def _get_thesis_section(section_id: str) -> tuple[int, dict[str, str]]:
        clean_section_id = (section_id or "").strip()
        for index, section in enumerate(THESIS_COMPLETE_SECTIONS, start=1):
            if section["id"] == clean_section_id:
                return index, section
        valid_ids = ", ".join(str(section["id"]) for section in THESIS_COMPLETE_SECTIONS)
        raise GeminiServiceError(f"Seccion de tesis no valida. Usa una de: {valid_ids}.")

    @staticmethod
    def _build_thesis_complete_section_prompt(
        source_plan_text: str,
        thesis_history: list[dict],
        section: dict[str, str],
        section_index: int,
        formal_data: dict[str, str] | None,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
    ) -> str:
        plan_block = GeminiService._truncate_text(source_plan_text, max_chars=32000)
        history_block = GeminiService._format_history(thesis_history)
        formal_data_block = GeminiService._format_formal_data(formal_data)
        sources_block = GeminiService._format_academic_sources(academic_sources or [])
        academic_context = format_academic_context(academic_profile)
        total_sections = len(THESIS_COMPLETE_SECTIONS)
        manual_name = (
            str((academic_profile or {}).get("manual_name") or "").strip()
            or "normativa academica de la facultad seleccionada"
        )
        min_references = int((academic_profile or {}).get("minimum_references") or 20)

        return (
            "Genera una etapa de la tesis final a partir del plan de tesis fuente.\n"
            f"Etapa actual: {section_index}/{total_sections} - {section['title']}\n\n"
            "Plan de tesis fuente obligatorio:\n"
            f"{plan_block or 'No se pudo recuperar el plan fuente.'}\n\n"
            "Historial de la tesis y etapas ya generadas:\n"
            f"{history_block}\n\n"
            "Datos formales disponibles:\n"
            f"{formal_data_block}\n\n"
            "Contexto academico obligatorio:\n"
            f"{academic_context}\n\n"
            "Referencias candidatas encontradas automaticamente:\n"
            f"{sources_block}\n\n"
            "Referencias normativas base:\n"
            f"- Universidad Privada de Tacna. {manual_name}.\n"
            "- Normativa nacional peruana, normas tecnicas, guias profesionales o marcos eticos pertinentes a la carrera.\n\n"
            "Objetivo especifico de esta etapa:\n"
            f"{section['focus']}\n\n"
            "Salida obligatoria de esta etapa:\n"
            f"{section['required_output']}\n\n"
            "Reglas de calidad para tesis:\n"
            "- Entrega solo el contenido de la etapa solicitada, empezando con el titulo exacto de la etapa.\n"
            "- Redacta como tesis, no como instrucciones para el estudiante ni como plan pendiente.\n"
            "- Conserva el titulo, variables/categorias, objetivos, metodologia y poblacion del plan fuente salvo que exista contradiccion evidente.\n"
            "- No uses placeholders entre corchetes. Si falta un dato formal, usa 'dato pendiente de registro' una sola vez.\n"
            "- No escribas que una seccion esta vacia. Desarrolla una version academica viable con la evidencia del plan.\n"
            "- No inventes resultados reales, muestras ejecutadas, p-valores, porcentajes, entrevistas realizadas, mediciones o pruebas de laboratorio no presentes en el plan.\n"
            "- Cuando no existan datos ejecutados, usa etiquetas honestas como 'resultado esperado', 'propuesta de validacion', 'criterio de evaluacion' o 'evidencia pendiente de levantamiento'.\n"
            "- En la etapa de resultados/propuesta, adapta el capitulo al entregable de la carrera seleccionada.\n"
            f"- En referencias, apunta a no menos de {min_references} fuentes si hay suficientes fuentes candidatas y normativas.\n"
            "- Usa tablas Markdown cuando fortalezcan metodologia, operacionalizacion, resultados, propuesta o anexos.\n"
            "- Mantiene coherencia entre todos los capitulos ya generados."
        )

    @staticmethod
    def _build_local_thesis_complete_section(
        source_plan_text: str,
        section: dict[str, str],
        section_index: int,
        formal_data: dict[str, str] | None = None,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
        unavailable_reason: str | None = None,
    ) -> str:
        tentative = GeminiService._build_tentative_plan_elements(
            source_plan_text,
            academic_profile=academic_profile,
        )
        warning = (
            f"\n\nNota tecnica: se uso una plantilla local porque el proveedor IA no completo la etapa. Detalle: {unavailable_reason}"
            if unavailable_reason
            else ""
        )
        return (
            f"{section['title']}\n\n"
            "Esta etapa debe desarrollarse directamente desde el plan de tesis seleccionado.\n\n"
            "Sintesis del plan fuente:\n"
            f"{GeminiService._truncate_text(source_plan_text, max_chars=1800)}\n\n"
            "Datos formales registrados:\n"
            f"{GeminiService._format_formal_data(formal_data)}\n\n"
            "Contexto academico:\n"
            f"{format_academic_context(academic_profile)}\n\n"
            "Contenido minimo esperado para esta etapa:\n"
            f"{section['required_output']}\n\n"
            "Elementos base para mantener coherencia:\n"
            f"- Titulo tentativo extraido: {tentative['title_1']}.\n"
            f"- Problema central: {tentative['problem']}.\n"
            f"- Objetivo general: {tentative['objective']}.\n"
            f"- Variables/categorias: {tentative['variables']}\n"
            f"- Unidad y datos: {tentative['unit']}\n\n"
            "Referencias candidatas:\n"
            f"{GeminiService._format_academic_sources(academic_sources or [])}"
            f"{warning}"
        )

    def generate_thesis_complete_section(
        self,
        source_plan_text: str,
        thesis_history: list[dict] | None,
        section_id: str,
        formal_data: dict[str, str] | None = None,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        academic_profile: dict | None = None,
    ) -> tuple[str, int, str, int]:
        clean_plan_text = (source_plan_text or "").strip()
        if not clean_plan_text:
            raise GeminiServiceError("No se pudo recuperar el contenido del plan de tesis fuente.")

        conversation_history = thesis_history or []
        section_index, section = self._get_thesis_section(section_id)
        discovery_history = [{"role": "user", "content": clean_plan_text}, *conversation_history]
        source_limit = 18 if section_id == "referencias_anexos" else 10
        academic_sources = self._discover_academic_sources(
            discovery_history,
            limit=source_limit,
            academic_profile=academic_profile,
        )
        prompt = self._build_thesis_complete_section_prompt(
            source_plan_text=clean_plan_text,
            thesis_history=conversation_history,
            section=section,
            section_index=section_index,
            formal_data=formal_data,
            academic_sources=academic_sources,
            academic_profile=academic_profile,
        )

        provider = self._normalize_ai_provider(ai_provider)
        try:
            text = self._generate_text(
                prompt,
                self._build_thesis_system_instruction(academic_profile),
                ai_provider=provider,
                ai_model=ai_model,
                temperature=0.2,
                max_output_tokens=max(
                    int(
                        self.settings.deepseek_chat_max_output_tokens
                        if provider == AI_PROVIDER_DEEPSEEK
                        else self.settings.gemini_review_max_output_tokens
                    ),
                    6144,
                ),
            )
        except GeminiServiceError as error:
            text = self._build_local_thesis_complete_section(
                source_plan_text=clean_plan_text,
                section=section,
                section_index=section_index,
                formal_data=formal_data,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason=error.message,
            )

        clean_text = (text or "").strip()
        if len(clean_text) < 500:
            clean_text = self._build_local_thesis_complete_section(
                source_plan_text=clean_plan_text,
                section=section,
                section_index=section_index,
                formal_data=formal_data,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason="respuesta insuficiente del proveedor IA",
            )

        return clean_text, section_index, str(section["title"]), len(THESIS_COMPLETE_SECTIONS)

    @staticmethod
    def thesis_plan_suggested_questions(
        missing_fields: list[str],
        next_phase: str,
    ) -> list[dict[str, str]]:
        if next_phase == "flujo_manual_faing" and not missing_fields:
            return []

        question_bank = {
            "Tema o idea central": {
                "id": "idea_central",
                "label": "Idea central",
                "question": "Resume en una frase que quieres investigar o desarrollar.",
                "placeholder": "Ejemplo: plataforma inteligente para automatizar un proceso documental o productivo.",
            },
            "Problema observable": {
                "id": "problema_observable",
                "label": "Problema observable",
                "question": "Que problema concreto observas y como se evidencia?",
                "placeholder": "Ejemplo: demoras, perdida de seguimiento, baja trazabilidad o poca comunicacion asesor-estudiante.",
            },
            "Contexto o delimitacion": {
                "id": "contexto",
                "label": "Contexto",
                "question": "Donde ocurre el problema y que alcance tendria el estudio?",
                "placeholder": "Ejemplo: Facultad de Ingenieria de una universidad, semestre 2026-I.",
            },
            "Unidad de analisis o poblacion": {
                "id": "unidad_analisis",
                "label": "Unidad de analisis",
                "question": "Quienes o que elementos seran analizados?",
                "placeholder": "Ejemplo: documentos digitalizados, usuarios administrativos, procesos o lotes de trabajo.",
            },
            "Variables o categorias": {
                "id": "variables",
                "label": "Variables",
                "question": "Que variables, categorias o factores quieres relacionar o mejorar?",
                "placeholder": "Ejemplo: sistema propuesto, eficiencia operativa, precision, seguridad o trazabilidad.",
            },
            "Objetivo o resultado esperado": {
                "id": "objetivo",
                "label": "Objetivo",
                "question": "Que resultado esperas lograr con la investigacion?",
                "placeholder": "Ejemplo: determinar si el sistema mejora tiempos, trazabilidad y satisfaccion.",
            },
            "Tipo, nivel o diseno preliminar": {
                "id": "metodo",
                "label": "Metodo preliminar",
                "question": "Que tipo de estudio imaginas y como lo comprobarias?",
                "placeholder": "Ejemplo: aplicado, descriptivo o preexperimental con medicion antes/despues.",
            },
            "Datos, instrumentos o tecnica": {
                "id": "datos_instrumentos",
                "label": "Datos e instrumentos",
                "question": "Que datos puedes recolectar y con que instrumentos?",
                "placeholder": "Ejemplo: encuestas, registros de sesiones, tiempos de atencion, rubricas o entrevistas.",
            },
            "Justificacion, importancia o factibilidad": {
                "id": "justificacion",
                "label": "Justificacion",
                "question": "Por que es importante y factible realizar este plan?",
                "placeholder": "Ejemplo: reduce carga administrativa, mejora seguimiento y existe acceso a usuarios/datos.",
            },
            "Antecedentes o base bibliografica": {
                "id": "antecedentes",
                "label": "Antecedentes",
                "question": "Tienes antecedentes, tesis o articulos base relacionados?",
                "placeholder": "Ejemplo: sistemas de seguimiento academico, tutoria universitaria o gestion de tesis.",
            },
        }

        source_fields = missing_fields or [
            "Problema observable",
            "Contexto o delimitacion",
            "Unidad de analisis o poblacion",
            "Variables o categorias",
        ]
        questions: list[dict[str, str]] = []
        seen: set[str] = set()
        for field in source_fields:
            question = question_bank.get(field)
            if not question or question["id"] in seen:
                continue
            questions.append(question)
            seen.add(question["id"])
            if len(questions) >= 5:
                break
        return questions

    @staticmethod
    def _normalize_for_matching(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        without_accents = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        return without_accents.lower()

    @staticmethod
    def _assess_thesis_plan_readiness(history: list[dict]) -> tuple[int, list[str], str]:
        user_text = "\n".join(
            str(message.get("content", ""))
            for message in history
            if (message.get("role") or "user") == "user"
        )
        normalized_text = GeminiService._normalize_for_matching(user_text)
        word_count = len(TOKEN_PATTERN.findall(normalized_text))

        missing_fields: list[str] = []
        matched_count = 0

        for field in THESIS_PLAN_REQUIRED_FIELDS:
            keywords = field["keywords"]
            is_matched = any(keyword in normalized_text for keyword in keywords)

            if field["label"] == "Tema o idea central" and word_count >= 12:
                is_matched = True

            if is_matched:
                matched_count += 1
            else:
                missing_fields.append(field["label"])

        score = round((matched_count / len(THESIS_PLAN_REQUIRED_FIELDS)) * 100)
        if word_count >= 120 and score < 70:
            score = min(score + 10, 70)
        elif word_count < 35:
            score = min(score, 35)

        next_phase = "entrevista_diagnostica"
        if score >= 70:
            next_phase = "flujo_manual_faing"

        return score, missing_fields, next_phase

    @staticmethod
    def _format_missing_fields(missing_fields: list[str]) -> str:
        if not missing_fields:
            return "- No se detectan vacios criticos para iniciar el esquema del manual."
        return "\n".join(f"- {field}" for field in missing_fields)

    @staticmethod
    def _build_thesis_plan_prompt(
        history: list[dict],
        readiness_score: int,
        missing_fields: list[str],
        next_phase: str,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
    ) -> str:
        history_block = GeminiService._format_history(history)
        sections = GeminiService.thesis_plan_manual_sections(academic_profile)
        sections_block = "\n".join(f"- {section}" for section in sections)
        missing_block = GeminiService._format_missing_fields(missing_fields)
        sources_block = GeminiService._format_academic_sources(academic_sources or [])
        academic_context = format_academic_context(academic_profile)
        faculty_label = (
            str((academic_profile or {}).get("faculty_acronym") or "").strip()
            or "la facultad seleccionada"
        )

        if next_phase == "flujo_manual_faing":
            expected_response = (
                "Como la informacion ya es suficiente, inicia el flujo normativo. "
                "Entrega un plan preliminar completo, con campos marcados como 'por validar' "
                "cuando el estudiante no haya dado evidencia. Incluye la matriz de consistencia "
                "preliminar al final."
            )
        else:
            expected_response = (
                "La informacion aun no es suficiente. No redactes todavia el plan completo. "
                "Haz una entrevista metodologica con preguntas concretas, agrupadas por prioridad. "
                "Puedes proponer un titulo tentativo solo si lo presentas como provisional."
            )

        return (
            "Historial de trabajo del plan de tesis:\n"
            f"{history_block}\n\n"
            "Referencias candidatas encontradas automaticamente:\n"
            f"{sources_block}\n\n"
            "Contexto academico obligatorio:\n"
            f"{academic_context}\n\n"
            f"Estructura obligatoria del plan segun {faculty_label}:\n"
            f"{sections_block}\n\n"
            "Criterios clave de plan de tesis que debes aplicar:\n"
            "- El titulo debe ser corto, informativo, especifico, conciso y menor a 20 palabras.\n"
            "- El titulo debe sugerir proposito, variables, unidad de analisis y, si corresponde, espacio y tiempo.\n"
            "- La descripcion del problema parte de la observacion, contextualiza, identifica causas, efectos, soluciones y variables.\n"
            "- La formulacion incluye una pregunta general y dos a tres preguntas especificas.\n"
            "- La justificacion se evalua desde criterios ambientales, sociales, economicos y cientificos cuando aplique.\n"
            "- Los objetivos usan verbos en infinitivo y debe existir un objetivo por cada pregunta.\n"
            "- Las hipotesis responden a las preguntas y deben tener respaldo bibliografico si son pertinentes.\n"
            "- La operacionalizacion precisa variables, indicadores y escalas de medicion.\n"
            "- El tipo puede ser basico o aplicado; el nivel puede ser exploratorio, descriptivo, correlacional, explicativo, predictivo o aplicativo.\n"
            "- El marco teorico incluye antecedentes cientificos, bases teoricas y terminos o conceptos clave segun la carrera.\n"
            "- El marco metodologico define diseno, acciones, instrumentos, poblacion/muestra y tecnicas de analisis.\n"
            "- El plan incluye los anexos, cronograma, presupuesto, bibliografia o indices que exija la normativa de la facultad.\n\n"
            "Diagnostico automatico de suficiencia:\n"
            f"- Puntaje: {readiness_score}/100\n"
            f"- Fase: {next_phase}\n"
            "- Informacion faltante:\n"
            f"{missing_block}\n\n"
            "Regla de avance:\n"
            f"{expected_response}\n\n"
            "Regla de autonomia del asesor:\n"
            "- No cierres con una lista de datos para que el estudiante la complete desde cero.\n"
            "- Responde esas preguntas con propuestas tentativas: titulos, variables, unidad de analisis, poblacion/muestra, instrumentos y tecnica de analisis.\n"
            "- Marca cada propuesta como 'por validar' cuando no haya evidencia suficiente.\n"
            "- Si falta bibliografia, usa las referencias candidatas y/o propone terminos de busqueda academicos concretos.\n"
            "- El estudiante debe validar y corregir, no construir todo desde cero.\n\n"
            "Formato si estas en entrevista diagnostica:\n"
            "1) Estado de la idea\n"
            "2) Lo que ya se sabe\n"
            "3) Borrador tentativo por validar\n"
            "4) Preguntas minimas del asesor\n"
            "5) Referencias candidatas y terminos de busqueda\n\n"
            "Formato si estas en flujo del manual:\n"
            "1) Diagnostico de suficiencia\n"
            "2) Plan de tesis segun la normativa de la facultad y carrera\n"
            "3) Matriz de consistencia preliminar\n"
            "4) Riesgos metodologicos y datos por validar\n"
            "5) Propuestas concretas para cerrar vacios\n"
            "6) Referencias candidatas y busqueda academica sugerida"
        )

    @staticmethod
    def _build_local_thesis_plan_advice(
        history: list[dict],
        readiness_score: int,
        missing_fields: list[str],
        next_phase: str,
        academic_sources: list[str] | None = None,
        academic_profile: dict | None = None,
        unavailable_reason: str | None = None,
    ) -> str:
        primary_idea = GeminiService._extract_primary_user_plan_idea(history)
        latest_idea = GeminiService._extract_latest_user_plan_idea(history)
        tentative = GeminiService._build_tentative_plan_elements(
            primary_idea or latest_idea,
            academic_profile=academic_profile,
        )
        missing_block = GeminiService._format_missing_fields(missing_fields[:7])
        sources_block = GeminiService._format_academic_sources(academic_sources or [])
        faculty_label = (
            str((academic_profile or {}).get("faculty_acronym") or "").strip()
            or "la facultad seleccionada"
        )

        if next_phase != "flujo_manual_faing":
            return (
                "1) Estado de la idea\n"
                f"La idea todavia esta en entrevista diagnostica ({readiness_score}/100). "
                "No conviene iniciar el esquema completo del manual hasta cerrar los vacios principales.\n\n"
                "2) Lo que ya se sabe\n"
                f"{tentative['idea_summary']}\n\n"
                "3) Borrador tentativo por validar\n"
                f"- Titulo tentativo 1: {tentative['title_1']} (por validar).\n"
                f"- Titulo tentativo 2: {tentative['title_2']} (por validar).\n"
                f"- Problema general tentativo: {tentative['problem']} (por validar).\n"
                f"- Objetivo general tentativo: {tentative['objective']} (por validar).\n"
                f"- Variables/categorias tentativas: {tentative['variables']}\n"
                f"- Unidad y datos tentativos: {tentative['unit']}\n\n"
                "4) Preguntas minimas del asesor\n"
                f"{missing_block}\n"
                "Responde solo lo que quieras corregir del borrador: contexto exacto, poblacion real, datos disponibles e instrumentos.\n\n"
                "5) Referencias candidatas y terminos de busqueda\n"
                f"{sources_block}\n"
                f"- Terminos sugeridos: {tentative['search_terms']}."
            )

        sections_block = "\n".join(
            f"- {section}"
            for section in GeminiService.thesis_plan_manual_sections(academic_profile)
        )
        return (
            "1) Diagnostico de suficiencia\n"
            f"La idea alcanza {readiness_score}/100. Se puede iniciar el flujo normativo de {faculty_label}, "
            "pero todo dato no declarado debe quedar como por validar.\n\n"
            "2) Plan de tesis segun la normativa de la facultad y carrera\n"
            f"{sections_block}\n\n"
            "Borrador inicial basado en la informacion entregada:\n"
            f"{tentative['idea_summary']}\n\n"
            f"- Titulo recomendado: {tentative['title_1']} (por validar).\n"
            f"- Problema general tentativo: {tentative['problem']} (por validar).\n"
            f"- Objetivo general tentativo: {tentative['objective']} (por validar).\n"
            f"- Variables/categorias tentativas: {tentative['variables']}\n"
            f"- Unidad y datos tentativos: {tentative['unit']}\n\n"
            "3) Matriz de consistencia preliminar\n"
            "Completa una fila por problema especifico con: formulacion del problema, objetivo, hipotesis, variable, indicador, metodo y estadistica.\n\n"
            "4) Riesgos metodologicos y datos por validar\n"
            f"{missing_block}\n\n"
            "5) Propuestas concretas para cerrar vacios\n"
            "- Delimita institucion, periodo, poblacion y muestra antes de cerrar el titulo.\n"
            "- Define indicadores medibles para cada variable o categoria.\n"
            "- Selecciona instrumentos y tecnica de analisis segun el enfoque y nivel real del estudio.\n\n"
            "6) Referencias candidatas y busqueda academica sugerida\n"
            f"{sources_block}"
        )

    def advise_thesis_plan(
        self,
        history: list[dict] | None = None,
        user_message: str = "",
        ai_provider: str | None = None,
        ai_model: str | None = None,
        academic_profile: dict | None = None,
    ) -> tuple[str, int, list[str], str]:
        conversation_history = history or []
        readiness_score, missing_fields, next_phase = self._assess_thesis_plan_readiness(
            conversation_history
        )
        academic_sources = self._discover_academic_sources(
            conversation_history,
            academic_profile=academic_profile,
        )
        prompt = self._build_thesis_plan_prompt(
            history=conversation_history,
            readiness_score=readiness_score,
            missing_fields=missing_fields,
            next_phase=next_phase,
            academic_sources=academic_sources,
            academic_profile=academic_profile,
        )

        if user_message:
            prompt = (
                f"{prompt}\n\n"
                "Ultimo mensaje del estudiante:\n"
                f"{user_message.strip()}"
            )

        provider = self._normalize_ai_provider(ai_provider)
        if provider == AI_PROVIDER_GEMINI and self._should_skip_remote_generation():
            fallback = self._build_local_thesis_plan_advice(
                history=conversation_history,
                readiness_score=readiness_score,
                missing_fields=missing_fields,
                next_phase=next_phase,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason=self._get_generation_unavailability_reason(),
            )
            return fallback, readiness_score, missing_fields, next_phase

        try:
            text = self._generate_text(
                prompt,
                self._build_thesis_plan_system_instruction(academic_profile),
                ai_provider=provider,
                ai_model=ai_model,
                temperature=0.25,
                max_output_tokens=max(
                    int(
                        self.settings.deepseek_chat_max_output_tokens
                        if provider == AI_PROVIDER_DEEPSEEK
                        else self.settings.gemini_review_max_output_tokens
                    ),
                    4096,
                ),
            )
        except GeminiServiceError as error:
            if not self._generation_fallback_warned:
                LOGGER.warning(
                    "Proveedor IA no disponible para plan de tesis, usando fallback local: %s",
                    error.message,
                )
                self._generation_fallback_warned = True

            fallback = self._build_local_thesis_plan_advice(
                history=conversation_history,
                readiness_score=readiness_score,
                missing_fields=missing_fields,
                next_phase=next_phase,
                academic_sources=academic_sources,
                academic_profile=academic_profile,
                unavailable_reason=error.message or self._get_generation_unavailability_reason(),
            )
            return fallback, readiness_score, missing_fields, next_phase

        if text and len(text.strip()) >= 500:
            return text, readiness_score, missing_fields, next_phase

        fallback = self._build_local_thesis_plan_advice(
            history=conversation_history,
            readiness_score=readiness_score,
            missing_fields=missing_fields,
            next_phase=next_phase,
            academic_sources=academic_sources,
            academic_profile=academic_profile,
            unavailable_reason="La respuesta del proveedor IA fue insuficiente.",
        )
        return fallback, readiness_score, missing_fields, next_phase

    @staticmethod
    def _truncate_text(value: str, max_chars: int = 700) -> str:
        text = (value or "").strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _extract_text_from_generation_response(response: object) -> str:
        if response is None:
            return ""

        direct_text = getattr(response, "text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        if isinstance(response, dict):
            text = response.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

        candidates = getattr(response, "candidates", None)
        if candidates is None and isinstance(response, dict):
            candidates = response.get("candidates")

        if not isinstance(candidates, list):
            return ""

        parts_text: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if isinstance(candidate, dict):
                content = candidate.get("content")

            parts = getattr(content, "parts", None)
            if isinstance(content, dict):
                parts = content.get("parts")

            if not isinstance(parts, list):
                continue

            for part in parts:
                text = getattr(part, "text", None)
                if isinstance(part, dict):
                    text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts_text.append(text.strip())

        return "\n".join(parts_text)

    @staticmethod
    def _prepare_document_for_review(
        chunks: list[str],
        max_chars: int = 260000,
    ) -> tuple[str, int]:
        formatted_chunks: list[str] = []
        total_chars = 0
        analyzed_chunks = 0

        for index, chunk in enumerate(chunks, start=1):
            content = (chunk or "").strip()
            if not content:
                continue

            block = f"[Fragmento {index}]\n{content}\n\n"
            if total_chars + len(block) > max_chars:
                break

            formatted_chunks.append(block)
            total_chars += len(block)
            analyzed_chunks += 1

        if not formatted_chunks:
            return "", 0

        return "".join(formatted_chunks).strip(), analyzed_chunks

    @staticmethod
    def _build_thesis_review_prompt(
        filename: str,
        total_chunks: int,
        analyzed_chunks: int,
        document_text: str,
        history: list[dict],
        user_request: str,
    ) -> str:
        history_block = GeminiService._format_history(history)
        request_block = (user_request or "").strip() or (
            "Evalua integralmente esta tesis y prioriza las mejoras de mayor impacto."
        )

        return (
            "Analiza integralmente la tesis y entrega retroalimentacion academica.\n"
            f"Archivo: {filename}\n"
            f"Fragmentos cargados para analisis: {analyzed_chunks} de {total_chunks}\n\n"
            "Solicitud actual del estudiante:\n"
            f"{request_block}\n\n"
            "Historial del chat de revision:\n"
            f"{history_block}\n\n"
            "Contenido de la tesis:\n"
            f"{document_text}\n\n"
            "Instrucciones de formato estrictas:\n"
            "- No incluyas saludos, presentaciones ni preambulos.\n"
            "- Inicia directamente en '1) Veredicto general'.\n"
            "- Desarrolla cada seccion con detalle metodologico y formal.\n"
            "- Usa listas cuando corresponda para mayor claridad.\n\n"
            "Responde con esta estructura exacta:\n"
            "1) Veredicto general (aprobable/no aprobable y por que)\n"
            "2) Fortalezas principales (3-6 puntos)\n"
            "3) Brechas o debilidades (3-8 puntos)\n"
            "4) Que le falta para mejorar (checklist accionable y priorizada)\n"
            "5) Recomendaciones concretas por capitulo o seccion\n"
            "6) Priorizacion final (alta, media, baja)"
        )

    @staticmethod
    def _build_local_thesis_review(
        thesis_text: str,
        analyzed_chunks: int,
        total_chunks: int,
        unavailable_reason: str | None = None,
    ) -> str:
        text = (thesis_text or "").lower()
        word_count = len(TOKEN_PATTERN.findall(text))

        expected_sections = [
            ("resumen", "Resumen"),
            ("introduccion", "Introduccion"),
            ("planteamiento", "Planteamiento del problema"),
            ("objetivos", "Objetivos"),
            ("justificacion", "Justificacion"),
            ("marco", "Marco teorico"),
            ("metodologia", "Metodologia"),
            ("resultados", "Resultados"),
            ("conclusiones", "Conclusiones"),
            ("referencias", "Referencias"),
        ]

        missing_sections = [
            label
            for token, label in expected_sections
            if token not in text
        ]

        strengths: list[str] = []
        if "objetiv" in text:
            strengths.append("Se detecta presencia de objetivos de investigacion.")
        if "metodolog" in text:
            strengths.append("Se identifica una seccion metodologica explicitada.")
        if "conclusion" in text:
            strengths.append("El documento incluye cierre con conclusiones.")
        if word_count >= 5000:
            strengths.append("La extension del contenido sugiere desarrollo suficiente para una tesis.")

        if not strengths:
            strengths.append("Se requiere mayor estructuracion para identificar fortalezas claras.")

        recommendations: list[str] = []
        for section in missing_sections[:5]:
            recommendations.append(f"Agregar o reforzar la seccion de {section}.")

        if word_count < 3500:
            recommendations.append(
                "Incrementar profundidad teorica y metodologica; el contenido parece breve para una tesis completa."
            )

        if not recommendations:
            recommendations.append(
                "Refinar la redaccion academica y sustentar mejor cada afirmacion con evidencia y citas."
            )

        verdict = "Aprobable con observaciones"
        if len(missing_sections) >= 5 or word_count < 2500:
            verdict = "No aprobable en su estado actual"

        missing_block = (
            "\n".join(f"- {section}" for section in missing_sections[:8])
            if missing_sections
            else "- No se detectan vacios estructurales evidentes a nivel de secciones base."
        )
        strengths_block = "\n".join(f"- {item}" for item in strengths)
        recommendations_block = "\n".join(f"- {item}" for item in recommendations)

        recommendations_by_section: list[str] = []
        if "objetiv" in text:
            recommendations_by_section.append("- Objetivos: validar correspondencia exacta con preguntas e hipotesis.")
        if "metodolog" in text:
            recommendations_by_section.append("- Metodologia: explicitar poblacion, muestra y justificacion estadistica.")
        if "resultado" in text:
            recommendations_by_section.append("- Resultados: separar descripcion de datos de interpretacion y juicios de valor.")
        if "discusi" in text:
            recommendations_by_section.append("- Discusion: contrastar hallazgos con antecedentes y justificar aceptacion/rechazo de hipotesis.")
        if "conclusion" in text:
            recommendations_by_section.append("- Conclusiones: alinear una conclusion por objetivo y evitar resultados nuevos.")

        if not recommendations_by_section:
            recommendations_by_section.append(
                "- Secciones clave: reforzar problema, objetivos, metodologia, resultados y conclusiones con evidencia."
            )

        priority_block = (
            "- Alta: corregir secciones ausentes y consistencia problema-objetivo-hipotesis.\n"
            "- Media: fortalecer citas, APA y justificacion metodologica.\n"
            "- Baja: pulir redaccion academica, estilo y formato de tablas/figuras."
        )

        return (
            "1) Veredicto general\n"
            f"{verdict}.\n\n"
            "2) Fortalezas principales\n"
            f"{strengths_block}\n\n"
            "3) Brechas o debilidades\n"
            f"{missing_block}\n\n"
            "4) Que le falta para mejorar\n"
            f"{recommendations_block}\n\n"
            "5) Recomendaciones concretas por capitulo o seccion\n"
            f"{'\n'.join(recommendations_by_section)}\n\n"
            "6) Priorizacion final\n"
            f"{priority_block}\n\n"
            f"Fragmentos evaluados: {analyzed_chunks} de {total_chunks}."
        )

    @staticmethod
    def _looks_like_complete_structured_review(text: str) -> bool:
        normalized = (text or "").lower()
        if len(normalized.strip()) < MIN_STRUCTURED_REVIEW_CHARS:
            return False

        required_sections = ("1)", "2)", "3)", "4)", "5)")
        hits = sum(1 for marker in required_sections if marker in normalized)
        return hits >= 4

    def _build_contextual_fallback_response(
        self,
        question: str,
        context_chunks: list[dict],
        unavailable_reason: str | None = None,
    ) -> str:
        if not context_chunks:
            return (
                "No pude usar el proveedor IA seleccionado en este momento y tampoco se recupero contexto util "
                "de la tesis. Intenta nuevamente en unos minutos o revisa la configuracion del modelo."
            )

        snippets: list[str] = []
        for index, chunk in enumerate(context_chunks[:8], start=1):
            content = self._truncate_text(chunk.get("content") or "", max_chars=950)
            if content:
                snippets.append(f"- Evidencia {index}: {content}")

        snippets_block = "\n".join(snippets) if snippets else "- Sin fragmentos legibles"
        return (
            "El proveedor IA seleccionado no estuvo disponible en este momento, pero aqui tienes una respuesta "
            "basada en los fragmentos recuperados de tu tesis.\n\n"
            "Diagnostico breve:\n"
            f"La pregunta fue: '{question}'. Con el contexto disponible, estos son los hallazgos mas cercanos.\n\n"
            "Hallazgos especificos (extractivos):\n"
            f"{snippets_block}\n\n"
            "Recomendaciones accionables:\n"
            "1. Vuelve a intentar la consulta para obtener respuesta generativa completa.\n"
            "2. Formula preguntas mas especificas (capitulo, variable, metodo) para aumentar precision.\n"
            "3. Contrasta cada hallazgo con citas y trazabilidad dentro del documento.\n"
            "4. Vuelve a intentar luego de revisar la configuracion del modelo seleccionado."
        )

    def review_thesis(
        self,
        filename: str,
        chunks: list[str],
        history: list[dict] | None = None,
        user_request: str = "",
        ai_provider: str | None = None,
        ai_model: str | None = None,
    ) -> tuple[str, int, int]:
        if not chunks:
            raise GeminiServiceError("No hay contenido para evaluar en la tesis.")

        document_text, analyzed_chunks = self._prepare_document_for_review(
            chunks,
            max_chars=max(int(self.settings.gemini_review_max_input_chars), 80000),
        )
        if not document_text or analyzed_chunks == 0:
            raise GeminiServiceError("No se pudo preparar el texto de la tesis para evaluacion.")

        analyzed_characters = len(document_text)
        prompt = self._build_thesis_review_prompt(
            filename=filename,
            total_chunks=len(chunks),
            analyzed_chunks=analyzed_chunks,
            document_text=document_text,
            history=history or [],
            user_request=user_request,
        )

        provider = self._normalize_ai_provider(ai_provider)
        if provider == AI_PROVIDER_GEMINI and self._should_skip_remote_generation():
            fallback = self._build_local_thesis_review(
                thesis_text=document_text,
                analyzed_chunks=analyzed_chunks,
                total_chunks=len(chunks),
                unavailable_reason=self._get_generation_unavailability_reason(),
            )
            return fallback, analyzed_chunks, analyzed_characters

        try:
            text = self._generate_text(
                prompt,
                THESIS_REVIEW_SYSTEM_PROMPT,
                ai_provider=provider,
                ai_model=ai_model,
                temperature=0.2,
                max_output_tokens=max(
                    int(
                        self.settings.deepseek_chat_max_output_tokens
                        if provider == AI_PROVIDER_DEEPSEEK
                        else self.settings.gemini_review_max_output_tokens
                    ),
                    1024,
                ),
            )
        except GeminiServiceError as error:
            if not self._generation_fallback_warned:
                LOGGER.warning(
                    "Proveedor IA no disponible para revision de tesis, usando fallback local: %s",
                    error.message,
                )
                self._generation_fallback_warned = True

            fallback = self._build_local_thesis_review(
                thesis_text=document_text,
                analyzed_chunks=analyzed_chunks,
                total_chunks=len(chunks),
                unavailable_reason=error.message or self._get_generation_unavailability_reason(),
            )
            return fallback, analyzed_chunks, analyzed_characters

        if text and self._looks_like_complete_structured_review(text):
            return text, analyzed_chunks, analyzed_characters

        if not self._generation_fallback_warned:
            LOGGER.warning("Respuesta de revision incompleta. Fallback local activado.")
            self._generation_fallback_warned = True

        fallback = self._build_local_thesis_review(
            thesis_text=document_text,
            analyzed_chunks=analyzed_chunks,
            total_chunks=len(chunks),
            unavailable_reason="La respuesta del proveedor IA fue incompleta o demasiado corta.",
        )
        return fallback, analyzed_chunks, analyzed_characters

    def stream_chat_response(
        self,
        question: str,
        context_chunks: list[dict],
        history: list[dict],
        ai_provider: str | None = None,
        ai_model: str | None = None,
    ) -> Generator[str, None, None]:
        provider = self._normalize_ai_provider(ai_provider)
        prompt = self._build_prompt(
            question=question,
            context_chunks=context_chunks,
            history=history,
        )

        if provider == AI_PROVIDER_DEEPSEEK:
            try:
                yield self._generate_with_deepseek(
                    prompt,
                    SYSTEM_PROMPT,
                    model=ai_model,
                    temperature=0.25,
                    max_output_tokens=max(int(self.settings.deepseek_chat_max_output_tokens), 1024),
                )
            except GeminiServiceError as error:
                yield self._build_contextual_fallback_response(
                    question,
                    context_chunks,
                    unavailable_reason=error.message,
                )
            return

        if self._should_skip_remote_generation():
            yield self._build_contextual_fallback_response(
                question,
                context_chunks,
                unavailable_reason=self._get_generation_unavailability_reason(),
            )
            return

        try:
            self._ensure_ready()
        except GeminiServiceError as error:
            self._mark_generation_unavailable(
                "Gemini no configurado o credenciales invalidas.",
                disable_remote=True,
            )
            if not self._generation_fallback_warned:
                LOGGER.warning(
                    "Gemini no disponible para chat, usando fallback contextual: %s",
                    error.message,
                )
                self._generation_fallback_warned = True

            yield self._build_contextual_fallback_response(
                question,
                context_chunks,
                unavailable_reason=self._get_generation_unavailability_reason(),
            )
            return

        client = self._get_client()

        model_errors: list[str] = []

        for model_name in self._candidate_chat_models(ai_model):
            try:
                response_stream = client.models.generate_content_stream(
                    model=model_name,
                    contents=self._prompt_with_system_instruction(prompt, SYSTEM_PROMPT),
                    config=types.GenerateContentConfig(
                        temperature=0.25,
                        max_output_tokens=max(
                            int(self.settings.gemini_chat_max_output_tokens),
                            1024,
                        ),
                    ),
                )
            except Exception as error:  # pragma: no cover - llamada externa
                model_errors.append(f"{model_name}: {error}")
                self._register_generation_failure(str(error))
                continue

            yielded_text = False
            try:
                for chunk in response_stream:
                    text = getattr(chunk, "text", "")
                    if text:
                        yielded_text = True
                        yield text
            except Exception as error:  # pragma: no cover - llamada externa
                model_errors.append(f"{model_name}: {error}")
                continue

            if yielded_text:
                self._clear_generation_unavailable()
                return

            model_errors.append(f"{model_name}: sin texto util")

        if not self._generation_fallback_warned:
            LOGGER.warning(
                "No se pudo generar respuesta con Gemini. Fallback contextual activado. %s",
                "; ".join(model_errors[:3]) if model_errors else "sin detalles",
            )
            self._generation_fallback_warned = True

        yield self._build_contextual_fallback_response(
            question,
            context_chunks,
            unavailable_reason=self._get_generation_unavailability_reason(),
        )


gemini_service = GeminiService()
