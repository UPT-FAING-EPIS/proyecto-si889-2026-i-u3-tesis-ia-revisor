from copy import deepcopy


PLAN_STRUCTURE_FAING = (
    "1. Datos generales: titulo, area y linea de investigacion, autor, asesor",
    "2. El problema de investigacion: descripcion, formulacion, justificacion, objetivos, hipotesis, variables, tipo y nivel",
    "3. Marco teorico: antecedentes, bases teoricas, definicion de terminos",
    "4. Marco metodologico: diseno, acciones, materiales/instrumentos, poblacion/muestra, analisis de datos",
    "5. Aspectos administrativos: cronograma, recursos humanos, presupuesto y financiamiento",
    "6. Referencias bibliograficas en APA vigente",
    "7. Anexos: matriz de consistencia",
)

PLAN_STRUCTURE_FAU = (
    "Caratula, indice de contenido, indice de tablas e indice de figuras",
    "Introduccion y linea de investigacion",
    "I. Planteamiento del problema: marco situacional, problema principal, problemas especificos, objetivos y justificacion",
    "II. Marco teorico: antecedentes de investigacion, conceptuales, contextuales, normativos y bases teoricas",
    "III. Metodologia: tipo, instrumentos, tecnicas, esquema metodologico e indice tentativo de la tesis",
    "Cronograma capitular, bibliografia y anexos",
)

PLAN_STRUCTURE_FACSA = (
    "Caratula del proyecto de investigacion",
    "Introduccion",
    "Capitulo I. El problema: planteamiento, formulacion, objetivos, justificacion y terminos basicos opcionales",
    "Capitulo II. Revision de la literatura: antecedentes internacionales, nacionales y locales; marco teorico",
    "Capitulo III. Hipotesis, variables y operacionalizacion de variables",
    "Capitulo IV. Metodologia de la investigacion: diseno, ambito, poblacion, muestra, criterios, tecnicas e instrumentos",
    "Referencias, cronograma, presupuesto y anexos segun corresponda",
)

PLAN_STRUCTURE_FACEM = (
    "I. Datos generales: titulo, linea de investigacion, autor, asesor, institucion y lugar",
    "II. Planteamiento del problema: descripcion, formulacion, justificacion, objetivos, hipotesis y variables",
    "III. Marco teorico: antecedentes internacionales, nacionales y regionales/locales; bases teoricas y conceptos basicos",
    "IV. Metodologia: tipo, nivel, diseno, poblacion, muestra, tecnicas, instrumentos, procesamiento y analisis",
    "V. Aspecto administrativo: cronograma, recursos y presupuesto",
    "VI. Referencias bibliograficas",
    "VII. Anexos: matriz de consistencia y esquema tentativo de tesis",
)

PLAN_STRUCTURE_FAEDCOH = (
    "I. Datos generales: titulo del plan, autor, linea y sublinea de investigacion",
    "II. El problema: planteamiento, formulacion y justificacion",
    "III. Objetivos de la investigacion: objetivo general y especificos",
    "IV. Marco teorico: antecedentes del estudio y bases teorico-cientificas",
    "V. Metodologia: hipotesis, operacionalizacion, tipo y diseno, ambito, tiempo social, poblacion, muestra, procedimientos, tecnicas e instrumentos",
    "VI. Aspecto administrativo: recursos, presupuesto y cronograma",
    "Referencias y anexos cuando correspondan a la modalidad",
)


FACULTIES = (
    {
        "id": "faing",
        "acronym": "FAING",
        "name": "Facultad de Ingenieria",
        "manual_name": "Manual para el desarrollo de trabajos de investigacion 2022 de la Facultad de Ingenieria",
        "plan_sections": PLAN_STRUCTURE_FAING,
        "minimum_references": 25,
        "careers": (
            {
                "id": "ingenieria_sistemas",
                "name": "Ingenieria de Sistemas",
                "default_research_line": "Sistemas de informacion, automatizacion, inteligencia artificial y ciberseguridad",
                "thesis_focus": "resolver problemas de informacion, automatizacion, seguridad, prediccion, gestion de procesos o toma de decisiones mediante tecnologia",
                "data_sources": "entrevistas, observacion del proceso, registros digitales, datasets, encuestas a usuarios, pruebas de usabilidad e indicadores antes/despues",
                "deliverable": "software funcional, prototipo, modelo computacional, dashboard, base de datos, arquitectura o propuesta de seguridad validada con datos",
                "method_guidance": "investigacion aplicada, descriptiva, correlacional, predictiva, aplicativo o preexperimental segun la solucion y los datos disponibles",
                "variables_hint": "solucion tecnologica propuesta, eficiencia del proceso, precision, seguridad, trazabilidad, satisfaccion de usuarios y calidad de informacion",
                "social_focus": "servicios publicos, universidades, salud, municipalidades, seguridad ciudadana y organizaciones de Tacna o del Peru",
                "problem_areas": (
                    "seguimiento academico y retroalimentacion de tesis",
                    "gestion documental y trazabilidad administrativa",
                    "alertas tempranas para servicios comunitarios",
                    "analitica de datos para toma de decisiones publicas",
                    "seguridad de informacion en instituciones locales",
                ),
                "search_terms": (
                    "information systems process automation public services",
                    "artificial intelligence decision support university management",
                    "cybersecurity information systems traceability",
                ),
            },
            {
                "id": "ingenieria_civil",
                "name": "Ingenieria Civil",
                "default_research_line": "Infraestructura, estructuras, transportes, hidraulica, geotecnia y gestion de obras",
                "thesis_focus": "diagnosticar, disenar, evaluar o mejorar infraestructura mediante criterios tecnicos, calculos, ensayos y modelamiento",
                "data_sources": "inspecciones, levantamientos topograficos, aforos, ensayos de materiales, muestras, drones, GIS, normas tecnicas y registros de obra",
                "deliverable": "memoria de calculo, diagnostico estructural, diseno vial o hidraulico, planos, metrados, presupuesto, simulacion o propuesta de mantenimiento",
                "method_guidance": "investigacion aplicada con medicion de campo, modelamiento tecnico, comparacion normativa y validacion por calculos o ensayos",
                "variables_hint": "estado de infraestructura, desempeno estructural, transitabilidad, capacidad hidraulica, costos, seguridad y vida util",
                "social_focus": "barrios urbanos, vias, colegios, hospitales, sistemas de agua, zonas inundables e infraestructura publica de Tacna o del Peru",
                "problem_areas": (
                    "deterioro de pavimentos urbanos",
                    "vulnerabilidad sismica de edificaciones publicas",
                    "deficiencias en redes de agua potable",
                    "riesgo de inundacion en zonas urbanas",
                    "control de costos y metrados con BIM",
                ),
                "search_terms": (
                    "pavement condition assessment urban roads",
                    "seismic vulnerability public buildings",
                    "hydraulic simulation flood risk urban areas",
                ),
            },
            {
                "id": "ingenieria_ambiental",
                "name": "Ingenieria Ambiental",
                "default_research_line": "Gestion ambiental, residuos, agua, aire, ecoeficiencia y evaluacion de impactos",
                "thesis_focus": "medir problemas ambientales reales y proponer soluciones de gestion, tratamiento, mitigacion u optimizacion",
                "data_sources": "mediciones ambientales, muestras de agua o lodos, caracterizacion de residuos, SIG, imagenes satelitales, encuestas y evaluacion normativa",
                "deliverable": "diagnostico ambiental, plan de gestion, propuesta de tratamiento, programa de ecoeficiencia, mapa tematico o ruta optimizada",
                "method_guidance": "investigacion aplicada, descriptiva, correlacional o experimental con mediciones, comparacion normativa y analisis estadistico",
                "variables_hint": "contaminacion, ecoeficiencia, residuos, calidad ambiental, cumplimiento normativo, percepcion ciudadana y efectividad de la propuesta",
                "social_focus": "municipalidades, juntas vecinales, instituciones educativas, cuencas, PTAR, mercados y espacios urbanos de Tacna o del Peru",
                "problem_areas": (
                    "gestion deficiente de residuos solidos",
                    "ruido ambiental en zonas urbanas",
                    "tratamiento de lodos y efluentes",
                    "ecoeficiencia en instituciones publicas",
                    "monitoreo multitemporal de cobertura ambiental",
                ),
                "search_terms": (
                    "solid waste management urban municipalities",
                    "environmental noise assessment urban areas",
                    "wastewater sludge treatment environmental management",
                ),
            },
            {
                "id": "ingenieria_electronica",
                "name": "Ingenieria Electronica",
                "default_research_line": "Automatizacion, control, IoT, telecomunicaciones, sensores y sistemas embebidos",
                "thesis_focus": "disenar e implementar prototipos o sistemas electronicos que midan, comuniquen, automaticen o controlen informacion del mundo fisico",
                "data_sources": "pruebas de laboratorio, sensores, microcontroladores, simulaciones, mediciones de precision, conectividad, calibracion y registros del prototipo",
                "deliverable": "prototipo electronico funcional, sistema IoT, firmware, red, modulo de control, tablero de monitoreo o simulacion validada",
                "method_guidance": "investigacion aplicada, experimental, preexperimental o de desarrollo tecnologico con pruebas tecnicas repetibles",
                "variables_hint": "precision de medicion, latencia, disponibilidad, consumo energetico, estabilidad, cobertura, respuesta de control y confiabilidad",
                "social_focus": "salud, agricultura, seguridad, energia, telecomunicaciones, monitoreo ambiental e infraestructura local",
                "problem_areas": (
                    "monitoreo IoT de variables ambientales",
                    "automatizacion de riego en zonas agricolas",
                    "sistemas embebidos para monitoreo de salud",
                    "control en tiempo real de procesos",
                    "mejora de conectividad en redes locales",
                ),
                "search_terms": (
                    "internet of things environmental monitoring sensors",
                    "embedded systems health monitoring",
                    "real time control systems industrial automation",
                ),
            },
            {
                "id": "ingenieria_industrial",
                "name": "Ingenieria Industrial",
                "default_research_line": "Productividad, calidad, seguridad, logistica, costos y mejora de procesos",
                "thesis_focus": "mejorar procesos, costos, productividad, calidad, seguridad o logistica mediante herramientas de gestion e ingenieria de operaciones",
                "data_sources": "observacion directa, cronometraje, entrevistas, encuestas, registros de produccion, costos, accidentes, mantenimiento, ventas o inventarios",
                "deliverable": "propuesta de mejora, plan de implementacion, VSM actual y futuro, modelo de gestion, plan SST, evaluacion economica u optimizacion",
                "method_guidance": "investigacion aplicada, descriptiva, explicativa o preexperimental con indicadores antes/despues o mejora proyectada",
                "variables_hint": "productividad, tiempos, costos, calidad, seguridad, inventarios, desperdicios, cumplimiento, satisfaccion y rentabilidad",
                "social_focus": "MYPE, plantas productivas, servicios publicos, hospitales, colegios, municipalidades y empresas de Tacna o del Peru",
                "problem_areas": (
                    "baja productividad en procesos operativos",
                    "accidentes y riesgos laborales",
                    "costos elevados por mala gestion de inventarios",
                    "demoras logisticas en servicios locales",
                    "deficiencias de calidad en procesos productivos",
                ),
                "search_terms": (
                    "lean manufacturing productivity improvement small companies",
                    "occupational safety risk management industrial engineering",
                    "inventory management optimization service companies",
                ),
            },
            {
                "id": "ingenieria_agroindustrial",
                "name": "Ingenieria Agroindustrial",
                "default_research_line": "Procesos agroindustriales, alimentos, bioproductos, calidad, inocuidad y aprovechamiento de residuos",
                "thesis_focus": "transformar materias primas o residuos en productos o procesos agroindustriales validados por laboratorio y analisis estadistico",
                "data_sources": "formulaciones, tratamientos, laboratorio fisico-quimico, microbiologico, sensorial, vida util, rendimiento y pruebas estadisticas",
                "deliverable": "formulacion optimizada, producto agroindustrial, proceso mejorado, ficha tecnica, evaluacion de vida util o aprovechamiento de residuos",
                "method_guidance": "investigacion aplicada y experimental con diseno de tratamientos, comparacion estadistica y criterios de calidad e inocuidad",
                "variables_hint": "formulacion, temperatura, tiempo, concentracion, rendimiento, aceptabilidad sensorial, vida util, inocuidad y calidad nutricional",
                "social_focus": "agricultores, agroindustrias, mercados, productos regionales, residuos de olivar, oregano, granada y cadenas alimentarias de Tacna",
                "problem_areas": (
                    "aprovechamiento de residuos agroindustriales",
                    "vida util de productos regionales",
                    "formulacion de alimentos funcionales",
                    "mejora de procesos de conservacion",
                    "calidad sensorial de productos agroindustriales",
                ),
                "search_terms": (
                    "agroindustrial waste valorization functional foods",
                    "shelf life food products sensory evaluation",
                    "food formulation optimization experimental design",
                ),
            },
        ),
    },
    {
        "id": "facsa",
        "acronym": "FACSA",
        "name": "Facultad de Ciencias de la Salud",
        "manual_name": "Manual de investigacion 2022 de la Facultad de Ciencias de la Salud",
        "plan_sections": PLAN_STRUCTURE_FACSA,
        "minimum_references": 20,
        "careers": (
            {
                "id": "medicina_humana",
                "name": "Medicina Humana",
                "default_research_line": "Salud publica, clinica, epidemiologia, diagnostico y factores de riesgo",
                "thesis_focus": "estudiar enfermedades, factores asociados, prevalencias, conocimientos, caracteristicas clinicas y resultados de salud en poblaciones reales",
                "data_sources": "historias clinicas, registros hospitalarios, pacientes, internos, encuestas, escalas clinicas, fichas de recoleccion y analisis estadistico",
                "deliverable": "evidencia clinica o epidemiologica con tablas, analisis estadistico y recomendaciones para prevencion, diagnostico, manejo o salud publica",
                "method_guidance": "observacional, transversal, caso-control, cohorte, descriptivo, correlacional o predictivo, con criterios eticos y de inclusion/exclusion",
                "variables_hint": "prevalencia, factores de riesgo, caracteristicas clinicas, adherencia, conocimiento, actitudes, comorbilidades y desenlaces de salud",
                "social_focus": "hospitales, centros de salud, adultos mayores, gestantes, escolares, pacientes y comunidades de Tacna o del Peru",
                "problem_areas": (
                    "factores asociados a enfermedades cronicas",
                    "adherencia a tratamientos en pacientes",
                    "conocimientos y actitudes sobre prevencion",
                    "salud mental en poblaciones vulnerables",
                    "caracteristicas clinico-epidemiologicas hospitalarias",
                ),
                "search_terms": (
                    "clinical epidemiology risk factors Peru",
                    "treatment adherence chronic disease patients",
                    "public health knowledge attitudes prevention",
                ),
            },
            {
                "id": "odontologia",
                "name": "Odontologia",
                "default_research_line": "Salud oral, materiales dentales, diagnostico, estetica, endodoncia y evidencia odontologica",
                "thesis_focus": "evaluar materiales, tecnicas, condiciones bucales o evidencia cientifica para mejorar decisiones clinicas odontologicas",
                "data_sources": "muestras in vitro, pacientes, escolares, radiografias, tomografias, protocolos de laboratorio, escalas, imagenes y revisiones sistematicas",
                "deliverable": "resultados comparativos de materiales o tecnicas, protocolo de laboratorio, evaluacion clinica, analisis de imagenes o revision sistematica",
                "method_guidance": "experimental in vitro, observacional clinico, transversal, comparativo o revision sistematica con criterios de seleccion y bioseguridad",
                "variables_hint": "rugosidad, color, microfiltracion, resistencia, actividad antimicrobiana, salud oral, percepcion estetica y diagnostico por imagen",
                "social_focus": "consultorios, clinicas odontologicas, escolares, pacientes y necesidades de salud oral de Tacna o del Peru",
                "problem_areas": (
                    "salud oral en escolares",
                    "efecto de bebidas sobre materiales dentales",
                    "comparacion de tecnicas endodonticas",
                    "percepcion estetica de la sonrisa",
                    "precision diagnostica en imagen odontologica",
                ),
                "search_terms": (
                    "dental materials microleakage color stability",
                    "oral health schoolchildren prevalence",
                    "endodontic techniques systematic review",
                ),
            },
            {
                "id": "tecnologia_medica",
                "name": "Tecnologia Medica",
                "default_research_line": "Laboratorio clinico, fisioterapia, salud funcional, diagnostico y rehabilitacion",
                "thesis_focus": "medir funciones corporales, dolor, rendimiento fisico o parametros de laboratorio para mejorar evaluacion, diagnostico o rehabilitacion",
                "data_sources": "pruebas funcionales, escalas de dolor, cuestionarios, mediciones musculoesqueleticas, muestras biologicas, parametros hematologicos e intervenciones",
                "deliverable": "protocolo de evaluacion, comparacion diagnostica, resultados funcionales o laboratoriales, intervencion terapeutica o recomendacion rehabilitadora",
                "method_guidance": "observacional, comparativo, preexperimental o experimental con medicion directa, criterios de inclusion y analisis estadistico",
                "variables_hint": "dolor, capacidad funcional, sueno, actividad fisica, equilibrio, coordinacion, parametros hematologicos, riesgo cardiovascular y sarcopenia",
                "social_focus": "adultos mayores, estudiantes, trabajadores, pacientes, laboratorios y servicios de rehabilitacion de Tacna o del Peru",
                "problem_areas": (
                    "dolor musculoesqueletico en estudiantes o trabajadores",
                    "capacidad funcional del adulto mayor",
                    "comparacion de tecnicas de laboratorio",
                    "actividad fisica y riesgo cardiovascular",
                    "intervenciones fisioterapeuticas para dolor lumbar",
                ),
                "search_terms": (
                    "musculoskeletal pain sleep quality students",
                    "functional capacity older adults physical therapy",
                    "clinical laboratory methods comparison hematology",
                ),
            },
        ),
    },
    {
        "id": "fau",
        "acronym": "FAU",
        "name": "Facultad de Arquitectura y Urbanismo",
        "manual_name": "Directiva de normas y procedimientos de trabajos de investigacion de la Facultad de Arquitectura y Urbanismo 2024",
        "plan_sections": PLAN_STRUCTURE_FAU,
        "minimum_references": 20,
        "careers": (
            {
                "id": "arquitectura",
                "name": "Arquitectura",
                "default_research_line": "Proyecto arquitectonico, urbanismo, espacio publico, sostenibilidad, patrimonio y equipamiento",
                "thesis_focus": "investigar un problema espacial o urbano y convertirlo en una propuesta arquitectonica sustentada con sitio, usuario, normativa y diseno",
                "data_sources": "analisis de sitio, registro fotografico, estudio de usuario, diagnostico urbano, clima, accesibilidad, normativa, referentes y requerimientos espaciales",
                "deliverable": "programa arquitectonico, concepto, memoria descriptiva, planos, cortes, elevaciones, zonificacion, renders, propuesta urbana, materialidad o modelo BIM",
                "method_guidance": "investigacion aplicada proyectual con diagnostico contextual, analisis normativo, criterios de diseno y validacion por programa y usuario",
                "variables_hint": "problema urbano-arquitectonico, necesidades del usuario, accesibilidad, habitabilidad, sostenibilidad, integracion urbana y calidad espacial",
                "social_focus": "equipamientos culturales, salud mental, espacios publicos, patrimonio, adulto mayor, turismo, educacion y barrios de Tacna o del Peru",
                "problem_areas": (
                    "deficit de equipamiento comunitario",
                    "deterioro de espacios publicos",
                    "necesidad de infraestructura para salud mental",
                    "revitalizacion urbana y patrimonial",
                    "equipamiento turistico o cultural sostenible",
                ),
                "search_terms": (
                    "architectural design community facilities urban regeneration",
                    "public space revitalization social sustainability",
                    "healthcare architecture mental health community center",
                ),
            },
        ),
    },
    {
        "id": "facem",
        "acronym": "FACEM",
        "name": "Facultad de Ciencias Empresariales",
        "manual_name": "Protocolo de plan de tesis 2024 de la Facultad de Ciencias Empresariales",
        "plan_sections": PLAN_STRUCTURE_FACEM,
        "minimum_references": 20,
        "careers": (
            {
                "id": "administracion_negocios_internacionales",
                "name": "Administracion de Negocios Internacionales",
                "default_research_line": "Comercio exterior, logistica internacional, competitividad, sostenibilidad y gestion internacional",
                "thesis_focus": "estudiar como una empresa o sector mejora competitividad, logistica, exportacion, importacion o gestion en mercados internacionales",
                "data_sources": "encuestas a empresarios o trabajadores, entrevistas, documentos empresariales, datos de exportacion/importacion y estadisticas sectoriales",
                "deliverable": "diagnostico empresarial o sectorial, analisis estadistico y propuesta de mejora logistica, exportadora, competitiva o de gestion internacional",
                "method_guidance": "descriptivo, correlacional, explicativo o aplicado, con encuestas, analisis documental y datos sectoriales",
                "variables_hint": "competitividad, gestion logistica, desempeno exportador, sostenibilidad, productividad, marketing internacional y calidad de servicio",
                "social_focus": "agroexportadoras, importadoras, MYPE, proyectos mineros, cadenas logisticas y sectores productivos de Tacna o del Peru",
                "problem_areas": (
                    "bajo desempeno exportador de empresas locales",
                    "deficiencias en gestion logistica internacional",
                    "escasa competitividad de sectores agroexportadores",
                    "gestion documentaria en comercio exterior",
                    "sostenibilidad en empresas exportadoras",
                ),
                "search_terms": (
                    "export performance logistics management competitiveness",
                    "international business sustainability export firms",
                    "foreign trade documentation process improvement",
                ),
            },
            {
                "id": "administracion_turistico_hotelera",
                "name": "Administracion Turistico-Hotelera",
                "default_research_line": "Gestion turistica, hoteleria, calidad de servicio, marketing turistico y sostenibilidad",
                "thesis_focus": "medir la experiencia del cliente o turista y proponer mejoras para servicios, destinos, hoteles, restaurantes o instituciones turisticas",
                "data_sources": "encuestas a turistas, huespedes, clientes, trabajadores, restaurantes, hoteles, agencias, entrevistas y observacion del servicio",
                "deliverable": "diagnostico turistico-hotelero, analisis de satisfaccion o fidelizacion y propuesta de marketing, servicio, posicionamiento o gestion sostenible",
                "method_guidance": "descriptivo, correlacional o aplicado con escalas de percepcion, SERVQUAL, encuestas y analisis estadistico",
                "variables_hint": "calidad de servicio, satisfaccion, fidelizacion, experiencia turistica, posicionamiento, marketing digital y sostenibilidad",
                "social_focus": "hoteles, restaurantes, agencias, atractivos turisticos, turistas chilenos, municipalidades y destinos de Tacna o del Peru",
                "problem_areas": (
                    "baja satisfaccion de turistas en servicios locales",
                    "debil posicionamiento de Tacna como destino",
                    "deficiencias de calidad en hoteles o restaurantes",
                    "escasa fidelizacion de clientes turisticos",
                    "marketing digital insuficiente en empresas turisticas",
                ),
                "search_terms": (
                    "tourism service quality satisfaction destination image",
                    "hotel customer loyalty SERVQUAL",
                    "digital marketing tourism hospitality",
                ),
            },
            {
                "id": "ciencias_contables_financieras",
                "name": "Ciencias Contables y Financieras",
                "default_research_line": "Tributacion, control interno, gestion financiera, rentabilidad, liquidez y cumplimiento",
                "thesis_focus": "analizar informacion economica, tributaria y financiera para explicar rentabilidad, liquidez, formalizacion, control o cumplimiento",
                "data_sources": "estados financieros, registros contables, declaraciones tributarias, ratios, reportes de morosidad, encuestas a contadores y documentos de gestion",
                "deliverable": "analisis financiero-contable, diagnostico tributario, propuesta de control interno, planeamiento tributario o mejora de gestion financiera",
                "method_guidance": "descriptivo, correlacional, explicativo o aplicado con analisis documental, ratios, encuestas y estadistica",
                "variables_hint": "liquidez, rentabilidad, morosidad, riesgo crediticio, control interno, formalizacion, obligaciones tributarias y flujo de caja",
                "social_focus": "MYPE, contribuyentes, instituciones publicas, empresas comerciales, municipalidades y sectores economicos de Tacna o del Peru",
                "problem_areas": (
                    "baja liquidez en microempresas",
                    "incumplimiento tributario de contribuyentes",
                    "debil control interno contable",
                    "morosidad y riesgo crediticio",
                    "rentabilidad afectada por mala gestion financiera",
                ),
                "search_terms": (
                    "tax compliance small businesses financial management",
                    "internal control accounting liquidity profitability",
                    "credit risk delinquency microfinance",
                ),
            },
            {
                "id": "economia_microfinanzas",
                "name": "Economia y Microfinanzas",
                "default_research_line": "Crecimiento economico, politica economica, indicadores sociales, exportaciones y microfinanzas",
                "thesis_focus": "explicar relaciones entre variables economicas y su impacto en crecimiento, exportaciones, inversion, inflacion o desarrollo",
                "data_sources": "series estadisticas, bases de organismos publicos, bancos, reportes oficiales, indicadores macroeconomicos y datos secundarios",
                "deliverable": "modelo economico o econometrico, graficos, interpretacion de resultados y recomendaciones de politica economica o microfinanzas",
                "method_guidance": "cuantitativo, explicativo, correlacional, longitudinal o econometrico con series de tiempo, panel o regresion",
                "variables_hint": "crecimiento, inflacion, tipo de cambio, exportaciones, inversion, gasto publico, empleo, recaudacion y colocaciones microfinancieras",
                "social_focus": "hogares, MYPE, sectores exportadores, gobierno regional, empleo, inversion y desarrollo economico de Tacna o del Peru",
                "problem_areas": (
                    "efecto del tipo de cambio en exportaciones",
                    "inflacion y poder adquisitivo local",
                    "gasto publico y crecimiento regional",
                    "microfinanzas y desarrollo de MYPE",
                    "empleo e indicadores sociales",
                ),
                "search_terms": (
                    "exchange rate exports economic growth Peru",
                    "public spending regional economic growth",
                    "microfinance small business development",
                ),
            },
            {
                "id": "ingenieria_comercial",
                "name": "Ingenieria Comercial",
                "default_research_line": "Marketing, ventas, gestion comercial, comportamiento del consumidor y estrategia competitiva",
                "thesis_focus": "entender clientes, mercados, marcas y ventas para proponer estrategias comerciales medibles",
                "data_sources": "encuestas a clientes, trabajadores o consumidores, entrevistas, escalas Likert, analisis de mercado, ventas y redes sociales",
                "deliverable": "diagnostico comercial, analisis de relacion entre variables y propuesta de marketing, fidelizacion, posicionamiento o gestion de clientes",
                "method_guidance": "descriptivo, correlacional, explicativo o aplicado con encuestas, modelos de calidad, estadistica y analisis comercial",
                "variables_hint": "marketing digital, satisfaccion, calidad de servicio, valor de marca, ventas, clima laboral, inteligencia comercial e innovacion",
                "social_focus": "comercios, servicios, consumidores digitales, emprendimientos, empresas locales y mercados de Tacna o del Peru",
                "problem_areas": (
                    "bajo posicionamiento de marcas locales",
                    "satisfaccion insuficiente de clientes",
                    "marketing digital poco efectivo",
                    "clima laboral y desempeno comercial",
                    "calidad de servicio en empresas de consumo",
                ),
                "search_terms": (
                    "digital marketing customer satisfaction brand equity",
                    "service quality customer loyalty commercial strategy",
                    "sales performance organizational climate",
                ),
            },
            {
                "id": "ingenieria_produccion_administracion",
                "name": "Ingenieria de la Produccion y Administracion",
                "default_research_line": "Produccion, calidad, administracion, procesos, productividad y gestion organizacional",
                "thesis_focus": "mejorar gestion, calidad, procesos y desempeno organizacional con enfoque productivo-administrativo",
                "data_sources": "encuestas a clientes o trabajadores, entrevistas, revision de procesos, indicadores de produccion, normas de calidad y documentos de gestion",
                "deliverable": "diagnostico organizacional o productivo, propuesta de procesos, sistema de calidad, plan de buenas practicas o estrategia de productividad",
                "method_guidance": "aplicado, descriptivo, correlacional o explicativo con indicadores, encuestas, analisis documental y evaluacion de procesos",
                "variables_hint": "gestion administrativa, calidad, productividad, satisfaccion, clima organizacional, ISO 9001, buenas practicas y desempeno",
                "social_focus": "agroindustrias, empresas de servicios, organizaciones productivas, clientes, trabajadores y sectores locales de Tacna o del Peru",
                "problem_areas": (
                    "baja productividad administrativa",
                    "deficiencias en gestion de calidad",
                    "clima organizacional y desempeno laboral",
                    "rotacion de personal en organizaciones",
                    "buenas practicas en procesos agroproductivos",
                ),
                "search_terms": (
                    "quality management productivity organizational performance",
                    "ISO 9001 process improvement service companies",
                    "organizational climate employee performance",
                ),
            },
        ),
    },
    {
        "id": "faedcoh",
        "acronym": "FAEDCOH",
        "name": "Facultad de Educacion, Comunicacion y Humanidades",
        "manual_name": "Directiva de modalidades de graduacion y titulacion de FAEDCOH",
        "plan_sections": PLAN_STRUCTURE_FAEDCOH,
        "minimum_references": 20,
        "careers": (
            {
                "id": "ciencias_comunicacion",
                "name": "Ciencias de la Comunicacion",
                "default_research_line": "Comunicacion digital, periodismo, imagen institucional, opinion publica y estrategias de comunicacion",
                "thesis_focus": "estudiar como mensajes, medios y redes influyen en publicos, marcas, instituciones y opinion social",
                "data_sources": "encuestas a publicos, analisis de contenido, publicaciones en redes sociales, entrevistas, engagement, observacion de campanas y discursos",
                "deliverable": "diagnostico comunicacional, analisis de percepcion o contenido, estrategia digital, plan de comunicacion o recomendaciones institucionales",
                "method_guidance": "descriptivo, correlacional, cualitativo, cuantitativo o mixto con analisis de contenido, encuestas y entrevistas",
                "variables_hint": "comunicacion digital, imagen de marca, opinion publica, credibilidad, engagement, comunicacion interna y percepcion de calidad",
                "social_focus": "instituciones publicas, medios locales, comunidades aimaras, universidades, marcas, organizaciones y ciudadania de Tacna o del Peru",
                "problem_areas": (
                    "desinformacion en redes sociales",
                    "debil comunicacion institucional",
                    "baja credibilidad de contenidos digitales",
                    "imagen de marca en servicios locales",
                    "comunicacion interna en organizaciones",
                ),
                "search_terms": (
                    "social media misinformation credibility communication",
                    "institutional communication public perception",
                    "digital media engagement brand image",
                ),
            },
            {
                "id": "educacion",
                "name": "Educacion",
                "default_research_line": "Aprendizaje, desarrollo infantil, estrategias pedagogicas, desempeno docente y convivencia educativa",
                "thesis_focus": "estudiar o mejorar procesos de aprendizaje y desarrollo mediante instrumentos, estrategias pedagogicas y trabajo directo en instituciones educativas",
                "data_sources": "observacion, fichas, rubricas, encuestas, pruebas de entrada y salida, entrevistas, sesiones de aprendizaje y programas educativos",
                "deliverable": "diagnostico educativo, instrumento, propuesta pedagogica, programa de intervencion, sesiones, resultados estadisticos y recomendaciones",
                "method_guidance": "descriptivo, correlacional, preexperimental, cuasi experimental o investigacion accion con criterios pedagogicos y evaluacion de aprendizaje",
                "variables_hint": "expresion oral, autonomia, psicomotricidad, lectoescritura, habilidades sociales, inteligencia emocional, clima institucional y desempeno docente",
                "social_focus": "instituciones educativas, ninos, estudiantes, docentes, padres de familia y comunidades escolares de Tacna o del Peru",
                "problem_areas": (
                    "dificultades de expresion oral en ninos",
                    "bajo desarrollo de habilidades sociales",
                    "problemas de lectoescritura",
                    "clima institucional y desempeno docente",
                    "estrategias ludicas para aprendizaje",
                ),
                "search_terms": (
                    "early childhood oral expression educational intervention",
                    "social skills students pedagogical strategies",
                    "literacy learning educational program",
                ),
            },
            {
                "id": "psicologia",
                "name": "Psicologia",
                "default_research_line": "Salud mental, conducta, bienestar, familia, adolescencia, instrumentos psicologicos e intervencion",
                "thesis_focus": "medir variables humanas y emocionales para explicar comportamientos, riesgos, bienestar o relaciones psicologicas en una poblacion",
                "data_sources": "pruebas psicologicas, escalas, cuestionarios, inventarios validados, entrevistas, muestras de adolescentes, estudiantes, trabajadores o familias",
                "deliverable": "analisis psicologico y estadistico, perfiles de riesgo, validacion de instrumentos, conclusiones y recomendaciones preventivas o psicoeducativas",
                "method_guidance": "descriptivo, correlacional, comparativo, psicometrico o explicativo con instrumentos validados, confiabilidad y consideraciones eticas",
                "variables_hint": "estres, bienestar, dependencia al celular, soledad, agresividad, apego, burnout, resiliencia, habitos de estudio y salud mental",
                "social_focus": "adolescentes, estudiantes, padres, trabajadores, familias, poblaciones vulnerables e instituciones de Tacna o del Peru",
                "problem_areas": (
                    "dependencia al celular en adolescentes",
                    "estres academico y bienestar psicologico",
                    "resiliencia en estudiantes",
                    "conducta agresiva y clima familiar",
                    "validacion de instrumentos psicologicos",
                ),
                "search_terms": (
                    "smartphone addiction adolescents psychological wellbeing",
                    "academic stress resilience students",
                    "psychometric validation psychological scales",
                ),
            },
        ),
    },
)


def list_academic_catalog() -> list[dict]:
    catalog: list[dict] = []
    for faculty in FACULTIES:
        catalog.append(
            {
                "id": faculty["id"],
                "acronym": faculty["acronym"],
                "name": faculty["name"],
                "careers": [
                    {
                        "id": career["id"],
                        "name": career["name"],
                        "supports_thesis_plan": True,
                    }
                    for career in faculty["careers"]
                ],
            }
        )
    return catalog


def get_faculty(faculty_id: str | None) -> dict | None:
    clean_faculty_id = (faculty_id or "").strip().lower()
    for faculty in FACULTIES:
        if faculty["id"] == clean_faculty_id:
            return faculty
    return None


def get_career_profile(faculty_id: str | None, career_id: str | None) -> dict | None:
    faculty = get_faculty(faculty_id)
    if not faculty:
        return None

    clean_career_id = (career_id or "").strip().lower()
    for career in faculty["careers"]:
        if career["id"] == clean_career_id:
            return {
                **deepcopy(career),
                "faculty_id": faculty["id"],
                "faculty_name": faculty["name"],
                "faculty_acronym": faculty["acronym"],
                "manual_name": faculty["manual_name"],
                "plan_sections": list(faculty["plan_sections"]),
                "minimum_references": faculty["minimum_references"],
                "supports_thesis_plan": True,
            }
    return None


def build_academic_profile(
    faculty_id: str | None,
    career_id: str | None,
    user_id: str | None = None,
) -> dict | None:
    profile = get_career_profile(faculty_id, career_id)
    if not profile:
        return None

    if user_id:
        profile["user_id"] = user_id

    return profile


def format_academic_context(profile: dict | None) -> str:
    if not profile:
        return (
            "Perfil academico no definido. Usa reglas generales y pide seleccionar "
            "facultad y carrera antes de generar un plan definitivo."
        )

    sections = "\n".join(f"- {section}" for section in profile.get("plan_sections", []))
    return (
        f"Facultad: {profile.get('faculty_name')} ({profile.get('faculty_acronym')}).\n"
        f"Carrera: {profile.get('name')}.\n"
        f"Normativa base: {profile.get('manual_name')}.\n"
        f"Linea sugerida: {profile.get('default_research_line')}.\n"
        f"Enfoque promedio de tesis: {profile.get('thesis_focus')}.\n"
        f"Fuentes de datos habituales: {profile.get('data_sources')}.\n"
        f"Entregable esperado: {profile.get('deliverable')}.\n"
        f"Guia metodologica: {profile.get('method_guidance')}.\n"
        f"Variables/categorias frecuentes: {profile.get('variables_hint')}.\n"
        f"Problemas sociales o institucionales pertinentes: {profile.get('social_focus')}.\n"
        f"Estructura normativa del plan:\n{sections}"
    )


def build_problem_suggestion_context(profile: dict | None) -> str:
    if not profile:
        return "Problemas sociales, institucionales o productivos de Tacna y del Peru."

    problem_areas = "; ".join(profile.get("problem_areas", []))
    return (
        f"Carrera: {profile.get('name')} ({profile.get('faculty_acronym')}). "
        f"Enfoque: {profile.get('thesis_focus')}. "
        f"Problemas pertinentes: {problem_areas}. "
        f"Impacto esperado: {profile.get('social_focus')}. "
        f"Entregable: {profile.get('deliverable')}."
    )


def build_fallback_problem_suggestions(profile: dict | None) -> list[dict[str, str]]:
    if not profile:
        return []

    career_name = profile.get("name") or "la carrera seleccionada"
    faculty_acronym = profile.get("faculty_acronym") or "UPT"
    areas = list(profile.get("problem_areas") or [])[:5]
    while len(areas) < 5:
        areas.append("necesidad social o institucional prioritaria")

    suggestions: list[dict[str, str]] = []
    for index, area in enumerate(areas, start=1):
        slug = area.replace(" ", "-").replace("/", "-").lower()[:42].strip("-")
        suggestions.append(
            {
                "id": f"{faculty_acronym.lower()}-{slug or index}",
                "title": f"{area.title()} en contextos de Tacna, 2026",
                "problem": (
                    f"En {career_name}, se observa el problema de {area} en instituciones, "
                    "empresas o comunidades locales, con efectos en la calidad del servicio, "
                    "la toma de decisiones y el bienestar de la poblacion."
                ),
                "community_impact": (
                    f"Permite orientar una propuesta o evidencia aplicada desde {career_name} "
                    "para mejorar decisiones, procesos o servicios relevantes para Tacna o el Peru."
                ),
                "research_context": (
                    f"Instituciones, empresas, usuarios, pacientes, estudiantes, registros o espacios "
                    f"vinculados a {career_name} en Tacna o a nivel nacional."
                ),
                "variables": (
                    f"{profile.get('variables_hint')}. Indicadores especificos por delimitar "
                    "segun poblacion, acceso a datos y normativa de la facultad."
                ),
            }
        )
    return suggestions
