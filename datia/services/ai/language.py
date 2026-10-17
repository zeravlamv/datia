
import re

class LanguageService:
    """
    Simple heuristic language detection and translation service.
    Supports: ES, EN, FR, DE, CA
    """
    
    LANGUAGES = {
        'es': {'stopwords': {'el', 'la', 'de', 'en', 'y', 'es', 'un', 'una', 'mejor', 'peor', 'listado', 'albaran', 'factura', 'ventas', 'informe', 'reporte'}},
        'en': {'stopwords': {'the', 'of', 'in', 'and', 'is', 'a', 'an', 'best', 'worst', 'list', 'delivery', 'note', 'invoice', 'order', 'sales', 'report'}},
        'fr': {'stopwords': {'le', 'la', 'les', 'de', 'du', 'en', 'et', 'est', 'meilleur', 'pire', 'liste', 'bon', 'livraison', 'facture', 'commande', 'ventes', 'rapport'}},
        'de': {'stopwords': {'der', 'die', 'das', 'von', 'und', 'ist', 'im', 'beste', 'schlechteste', 'liste', 'lieferschein', 'rechnung', 'bestellung', 'verkauf', 'bericht'}},
        'ca': {'stopwords': {'el', 'la', 'de', 'en', 'i', 'és', 'un', 'una', 'amb', 'millor', 'pitjor', 'llistat', 'albara', 'factura', 'comanda', 'vendes', 'informe'}},
        'pt': {'stopwords': {'o', 'a', 'de', 'em', 'e', 'é', 'um', 'uma', 'melhor', 'pior', 'lista', 'fatura', 'vendas', 'relatorio', 'encomenda'}},
        'it': {'stopwords': {'il', 'la', 'di', 'in', 'e', 'è', 'un', 'una', 'migliore', 'peggiore', 'elenco', 'fattura', 'vendite', 'rapporto', 'ordine'}},
        'gl': {'stopwords': {'o', 'a', 'de', 'en', 'e', 'é', 'un', 'unha', 'mellor', 'peor', 'listaxe', 'factura', 'vendas', 'informe', 'pedido'}},
        'eu': {'stopwords': {'a', 'bat', 'eta', 'da', 'onena', 'txarrena', 'zerrenda', 'faktura', 'salmentak', 'txostena', 'eskaera'}}
    }

    # [NEW] Explicit names for detection
    LANGUAGE_NAMES = {
        'es': ['español', 'spanish', 'castellano', 'espanglish'],
        'en': ['english', 'ingles', 'inglés', 'anglais'],
        'fr': ['french', 'frances', 'francés', 'français'],
        'de': ['german', 'aleman', 'alemán', 'deutsch'],
        'ca': ['catalan', 'català', 'valencia', 'valencià'],
        'pt': ['portuguese', 'portugues', 'portugués', 'português'],
        'it': ['italian', 'italiano'],
        'gl': ['galician', 'gallego', 'galego'],
        'eu': ['basque', 'vasco', 'euskera']
    }

    # [NEW] Common unsupported languages to detect
    UNSUPPORTED_LANGUAGES = {
        'ru': ['russian', 'ruso', 'русский'],
        'zh': ['chinese', 'chino', '中文'],
        'ja': ['japanese', 'japones', 'japonés', '日本語']
    }
    
    TRANSLATIONS = {
        'report_intro': {
            'es': "El ejercicio {ejercicio} presenta un rendimiento <b>{adj}</b>, con un aumento de ventas del <b>{growth:+.1f}%</b> respecto al año anterior.",
            'en': "Fiscal year {ejercicio} shows <b>{adj}</b> performance, with a sales increase of <b>{growth:+.1f}%</b> vs previous year.",
            'fr': "L'exercice {ejercicio} affiche une performance <b>{adj}</b>, avec une augmentation des ventes de <b>{growth:+.1f}%</b> par rapport à l'année précédente.",
            'de': "Das Geschäftsjahr {ejercicio} zeigt eine <b>{adj}</b> Leistung, mit einem Umsatzanstieg von <b>{growth:+.1f}%</b> gegenüber dem Vorjahr.",
            'ca': "L'exercici {ejercicio} presenta un rendiment <b>{adj}</b>, amb un augment de vendes del <b>{growth:+.1f}%</b> respecte a l'any anterior.",
            'pt': "O exercício {ejercicio} apresenta um desempenho <b>{adj}</b>, com um aumento de vendas de <b>{growth:+.1f}%</b> em relação ao ano anterior.",
            'it': "L'esercizio {ejercicio} mostra una performance <b>{adj}</b>, con un aumento delle vendite del <b>{growth:+.1f}%</b> rispetto all'anno precedente.",
            'gl': "O exercicio {ejercicio} presenta un rendemento <b>{adj}</b>, cun aumento de vendas do <b>{growth:+.1f}%</b> respecto ao ano anterior.",
            'eu': "{ejercicio} ekitaldiak <b>{adj}</b> errendimendua du, salmenten <b>{growth:+.1f}%</b> igoerarekin aurreko urtearekiko."
        },
        'report_costs': {
            'es': "Se han soportado unos costes de <b>{coste}</b>, dejando un margen bruto del <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'en': "Costs incurred were <b>{coste}</b>, leaving a gross margin of <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'fr': "Les coûts supportés s'élèvent à <b>{coste}</b>, laissant une marge brute de <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'de': "Die Kosten beliefen sich auf <b>{coste}</b>, was eine Bruttomarge von <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp) ergibt.",
            'ca': "S'han suportat uns costos de <b>{coste}</b>, deixant un marge brut del <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'pt': "Foram suportados custos de <b>{coste}</b>, deixando uma margem bruta de <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'it': "Sono stati sostenuti costi per <b>{coste}</b>, lasciando un margine lordo del <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'gl': "Soportáronse uns custos de <b>{coste}</b>, deixando unha marxe bruta do <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp).",
            'eu': "<b>{coste}</b>-ko kostuak jasan dira, <b>{margin:.1f}%</b> ({delta_margin:+.1f} pp) marjina gordina utziz."
        },
        'report_risk_high': {
            'es': "⚠️ <b>Riesgo Alto de Concentración</b>: Los 5 mejores clientes representan más de la mitad de tu facturación ({pct:.0f}%).",
            'en': "⚠️ <b>High Concentration Risk</b>: Top 5 clients represent more than half of your revenue ({pct:.0f}%).",
            'fr': "⚠️ <b>Risque de Concentration Élevé</b>: Les 5 meilleurs clients représentent plus de la moitié de votre chiffre d'affaires ({pct:.0f}%).",
            'de': "⚠️ <b>Hohes Konzentrationsrisiko</b>: Die Top 5 Kunden machen mehr als die Hälfte Ihres Umsatzes aus ({pct:.0f}%).",
            'ca': "⚠️ <b>Risc Alt de Concentració</b>: Els 5 millors clients representen més de la meitat de la teva facturació ({pct:.0f}%).",
            'pt': "⚠️ <b>Alto Risco de Concentração</b>: Os 5 melhores clientes representam mais da metade da sua faturação ({pct:.0f}%).",
            'it': "⚠️ <b>Alto Rischio di Concentrazione</b>: I 5 migliori clienti rappresentano più della metà del tuo fatturato ({pct:.0f}%).",
            'gl': "⚠️ <b>Risco Alto de Concentración</b>: Os 5 mellores clientes representan máis da metade da túa facturación ({pct:.0f}%).",
            'eu': "⚠️ <b>Kontzentrazio Arrisku Handia</b>: 5 bezero onenek zure fakturazioaren erdia baino gehiago ordezkatzen dute ({pct:.0f}%)."
        },
        'report_forecast': {
            'es': "<br><br>💡 <b>Previsión</b>: Siguiendo la tendencia actual (avg {avg}/mes), se estiman unas ventas de <b>{total}</b> para el próximo trimestre.",
            'en': "<br><br>💡 <b>Forecast</b>: Following current trend (avg {avg}/mo), sales of <b>{total}</b> are estimated for the next quarter.",
            'fr': "<br><br>💡 <b>Prévision</b>: Suivant la tendance actuelle (moy {avg}/mois), des ventes de <b>{total}</b> sont estimées pour le prochain trimestre.",
            'de': "<br><br>💡 <b>Prognose</b>: Dem aktuellen Trend folgend (Ø {avg}/Monat), werden Umsätze von <b>{total}</b> für das nächste Quartal geschätzt.",
            'ca': "<br><br>💡 <b>Previsió</b>: Seguint la tendència actual (mitj {avg}/mes), s'estimen unes vendes de <b>{total}</b> per al pròxim trimestre.",
            'pt': "<br><br>💡 <b>Previsão</b>: Seguindo a tendência atual (méd {avg}/mês), estimam-se vendas de <b>{total}</b> para o próximo trimestre.",
            'it': "<br><br>💡 <b>Previsione</b>: Seguendo la tendenza attuale (media {avg}/mese), si stimano vendite per <b>{total}</b> per il prossimo trimestre.",
            'gl': "<br><br>💡 <b>Previsión</b>: Seguindo a tendencia actual (med {avg}/mes), estímanse unhas vendas de <b>{total}</b> para o próximo trimestre.",
            'eu': "<br><br>💡 <b>Aurreikuspena</b>: Egungo joerari jarraituz (batez beste {avg}/hilean), hurrengo hiruhilekorako <b>{total}</b>-eko salmentak estimatzen dira."
        },
        'no_data': {
            'es': "No hay datos de {label} para {ejercicio}.",
            'en': "No data found for {label} in {ejercicio}.",
            'fr': "Aucune donnée trouvée pour {label} en {ejercicio}.",
            'de': "Keine Daten für {label} in {ejercicio} gefunden.",
            'ca': "No hi ha dades de {label} per a {ejercicio}.",
            'pt': "Não há dados de {label} para {ejercicio}.",
            'it': "Nessun dato trovato per {label} nel {ejercicio}.",
            'gl': "Non hai datos de {label} para {ejercicio}.",
            'eu': "Ez dago {label}-ren daturik {ejercicio}-rako."
        },
        'card_sales': {
            'es': "En {label}, las ventas fueron de <b>{neto}</b>.",
            'en': "In {label}, sales were <b>{neto}</b>.",
            'fr': "En {label}, les ventes étaient de <b>{neto}</b>.",
            'de': "In {label} betrugen die Verkäufe <b>{neto}</b>.",
            'ca': "A {label}, les vendes van ser de <b>{neto}</b>.",
            'pt': "Em {label}, as vendas foram de <b>{neto}</b>.",
            'it': "In {label}, le vendite sono state di <b>{neto}</b>.",
            'gl': "En {label}, as vendas foron de <b>{neto}</b>.",
            'eu': "{label}-(e)n, salmentak <b>{neto}</b> izan ziren."
        },
        'card_margin': {
            'es': " El margen bruto fue del <b>{pct}%</b> ({val}).",
            'en': " Gross margin was <b>{pct}%</b> ({val}).",
            'fr': " La marge brute était de <b>{pct}%</b> ({val}).",
            'de': " Die Bruttomarge betrug <b>{pct}%</b> ({val}).",
            'ca': " El marge brut va ser del <b>{pct}%</b> ({val}).",
            'pt': " A margem bruta foi de <b>{pct}%</b> ({val}).",
            'it': " Il margine lordo è stato del <b>{pct}%</b> ({val}).",
            'gl': " A marxe bruta foi do <b>{pct}%</b> ({val}).",
            'eu': " Marjina gordina <b>{pct}%</b> ({val}) izan zen."
        },
        'card_ticket': {
            'es': " El ticket medio se situó en <b>{val}</b> ({ops} operaciones).",
            'en': " Average ticket was <b>{val}</b> ({ops} operations).",
            'fr': " Le panier moyen était de <b>{val}</b> ({ops} opérations).",
            'de': " Der Durchschnittsbon lag bei <b>{val}</b> ({ops} Transaktionen).",
            'ca': " El tiquet mitjà es va situar en <b>{val}</b> ({ops} operacions).",
            'pt': " O ticket médio situou-se em <b>{val}</b> ({ops} operações).",
            'it': " Lo scontrino medio si è attestato a <b>{val}</b> ({ops} operazioni).",
            'gl': " O ticket medio situouse en <b>{val}</b> ({ops} operacións).",
            'eu': " Batez besteko tiketa <b>{val}</b>-n kokatu zen ({ops} eragiketa)."
        },
        'chart_title': {
            'es': "Evolución {label} {ejercicio}",
            'en': "{label} Evolution {ejercicio}",
            'fr': "Évolution {label} {ejercicio}",
            'de': "Entwicklung {label} {ejercicio}",
            'ca': "Evolució {label} {ejercicio}",
            'pt': "Evolução {label} {ejercicio}",
            'it': "Evoluzione {label} {ejercicio}",
            'gl': "Evolución {label} {ejercicio}",
            'eu': "{label} Bilakaera {ejercicio}"
        },
        'list_title': {
            'es': "Listado {label} {ejercicio}",
            'en': "{label} List {ejercicio}",
            'fr': "Liste {label} {ejercicio}",
            'de': "Liste {label} {ejercicio}",
            'ca': "Llistat {label} {ejercicio}",
            'pt': "Listagem {label} {ejercicio}",
            'it': "Elenco {label} {ejercicio}",
            'gl': "Listaxe {label} {ejercicio}",
            'eu': "{label} Zerrenda {ejercicio}"
        },
        'ranking_title': {
            'es': "Ranking {label} {ejercicio} (Top {limit})",
            'en': "{label} Ranking {ejercicio} (Top {limit})",
            'fr': "Classement {label} {ejercicio} (Top {limit})",
            'de': "Rangliste {label} {ejercicio} (Top {limit})",
            'ca': "Rànquing {label} {ejercicio} (Top {limit})",
            'pt': "Ranking {label} {ejercicio} (Top {limit})",
            'it': "Classifica {label} {ejercicio} (Top {limit})",
            'gl': "Ranking {label} {ejercicio} (Top {limit})",
            'eu': "{label} Ranking-a {ejercicio} (Top {limit})"
        },
        'generative_success': {
            'es': "Aquí tienes los datos encontrados para: {question}",
            'en': "Here is the data found for: {question}",
            'fr': "Voici les données trouvées pour : {question}",
            'de': "Hier sind die für {question} gefundenen Daten",
            'ca': "Aquí tens les dades trobades per a: {question}",
            'pt': "Aqui estão os dados encontrados para: {question}",
            'it': "Ecco i dati trovati per: {question}",
            'gl': "Aquí tes os datos atopados para: {question}",
            'eu': "Hemen dituzu aurkitutako datuak honetarako: {question}"
        },
        'generative_error': {
            'es': "He intentado generar una consulta, pero ha fallado: {error}",
            'en': "I tried to generate a query, but it failed: {error}",
            'fr': "J'ai essayé de générer une requête, mais cela a échoué : {error}",
            'de': "Ich habe versucht, eine Abfrage zu erstellen, aber es ist fehlgeschlagen: {error}",
            'ca': "He intentat generar una consulta, però ha fallat: {error}",
            'pt': "Tentei gerar uma consulta, mas falhou: {error}",
            'it': "Ho tentato di generare una query, ma è fallita: {error}",
            'gl': "Tentei xerar unha consulta, pero fallou: {error}",
            'eu': "Kontsulta bat sortzen saiatu naiz, baina huts egin du: {error}"
        },
        'destructive_error': {
            'es': "Lo siento, no puedo ejecutar consultas destructivas.",
            'en': "Sorry, I cannot execute destructive queries.",
            'fr': "Désolé, je ne peux pas exécuter de requêtes destructrices.",
            'de': "Entschuldigung, ich kann keine zerstörerischen Abfragen ausführen.",
            'ca': "Ho sento, no puc executar consultes destructives.",
            'pt': "Desculpe, não posso executar consultas destrutivas.",
            'it': "Spiacente, non posso eseguire query distruttive.",
            'gl': "Sentímolo, non podo executar consultas destrutivas.",
            'eu': "Barkatu, ezin dut kontsulta suntsitzailerik exekutatu."
        },
        'unavailable_error': {
            'es': "Traducción no disponible, contacte con el implementador",
            'en': "Translation not available, please contact the implementer",
            'fr': "Traduction non disponible, veuillez contacter l'implémenteur",
            'de': "Übersetzung nicht verfügbar, bitte wenden Sie sich an den Implementierer",
            'ca': "Traducció no disponible, contacteu amb l'implementador",
            'pt': "Tradução indisponível, entre em contato com o implementador",
            'it': "Traduzione non disponibile, contattare l'implementatore",
            'gl': "Tradución non dispoñible, contacte co implementador",
            'eu': "Itzulpena ez dago eskuragarri, jarri harremanetan inplementatzailearekin",
            'ru': "Перевод недоступен, пожалуйста, свяжитесь с разработчиком",
            'zh': "翻译不可用，请联系实施者",
            'ja': "翻訳は利用できません。実装者にお問い合わせください"
        },
        'changing_language': {
            'es': "Cambiando idioma a {name}...",
            'en': "Switching language to {name}...",
            'fr': "Changement de langue vers {name}...",
            'de': "Sprache ändern zu {name}...",
            'ca': "Canviant l'idioma a {name}...",
            'pt': "Alterando idioma para {name}...",
            'it': "Cambio lingua in {name}...",
            'gl': "Cambiando idioma a {name}...",
            'eu': "Hizkuntza {name}-ra aldatzen..."
        }
    }

    @staticmethod
    def detect(text: str) -> str:
        words = set(re.findall(r'\w+', text.lower()))
        scores = {}
        for lang, data in LanguageService.LANGUAGES.items():
            intersection = words & data['stopwords']
            scores[lang] = len(intersection)
            
        # Default to ES if no clear winner
        best_lang = max(scores, key=scores.get)
        if scores[best_lang] == 0:
            return 'es'
        return best_lang
    
    @staticmethod
    def check_explicit_switch(text: str) -> tuple[str, bool]:
        """
        Checks if the text contains an explicit request for a language.
        Returns: (lang_code or None, is_supported)
        """
        text_lower = text.lower()
        
        # 1. Check Supported
        for code, names in LanguageService.LANGUAGE_NAMES.items():
            for name in names:
                # Use regex boundries to avoid partial matches (e.g. "german" in "germany" is fine-ish but "ruso" in "intruso" is bad)
                if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
                    return code, True
                    
        # 2. Check Unsupported
        for code, names in LanguageService.UNSUPPORTED_LANGUAGES.items():
            for name in names:
                if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
                    return code, False
                    
        return None, False

    @staticmethod
    def get_text(key: str, lang: str, **kwargs) -> str:
        templates = LanguageService.TRANSLATIONS.get(key, {})
        # Fallback to ES
        tmpl = templates.get(lang) or templates.get('es', '')
        return tmpl.format(**kwargs)
