// Interface text catalogues. Every key exists in both languages: the English
// catalogue is typed against the French one, so a missing key fails the build.
// Placeholders use {name} and are filled by t(key, { name: value }).

export const fr = {
  "app.preview": "Aperçu, moteurs simulés",
  "app.offline": "Hors ligne",

  "nav.label": "Navigation",
  "nav.project": "Projet",
  "nav.steps": "Étapes du projet",
  "nav.start": "Démarrage",
  "nav.overview": "Vue d'ensemble",
  "nav.framework": "Cadre de résultats",
  "nav.indicators": "Indicateurs",
  "nav.data": "Données",
  "nav.report": "Rapport",
  "nav.soon": "Disponible dans une prochaine version",

  "side.fold": "Replier la barre latérale",
  "side.version": "Version {version}",
  "side.theme": "Changer de thème",
  "side.language": "Langue de l'interface",

  "start.title": "Démarrage",
  "start.lead":
    "Cette première version vérifie que l'application et ses deux moteurs de calcul fonctionnent sur votre ordinateur, sans connexion internet.",

  "engines.title": "Moteurs de calcul",
  "engines.recheck": "Vérifier à nouveau",
  "engines.ui": "Interface",
  "engines.python": "Moteur Python",
  "engines.r": "Moteur statistique R",
  "engines.pythonDetail": "Python {python}, polars {polars}, moteur {engine}",
  "engines.rDetail": "R {r}, survey {survey}, nanoarrow {nanoarrow}",
  "engines.missing": "absent",
  "engines.starting": "Démarrage en cours",
  "engines.rStarting": "Démarrage en cours, quelques secondes",
  "engines.unavailable": "Indisponible",
  "engines.logs": "Journal du moteur : {path}",

  "status.readyFeminine": "Prête",
  "status.ready": "Prêt",
  "status.error": "Erreur",
  "status.waiting": "En attente",

  "demo.title": "Calcul de démonstration",
  "demo.lead":
    "Proportion de filles de 6 à 11 ans scolarisées, sur 612 ménages fictifs. Le calcul est fait par R, comme le seront tous les calculs de l'application.",
  "demo.designLabel": "Type de calcul",
  "demo.survey": "Avec plan d'enquête",
  "demo.simple": "Échantillon simple",
  "demo.run": "Lancer le calcul",
  "demo.running": "Calcul en cours",
  "demo.failed": "Le calcul n'a pas abouti",
  "demo.ci": "Intervalle de confiance à {level} : {low} à {high}",
  "demo.counts": "{x} filles scolarisées sur {n}.",
  "demo.showScript": "Voir le script R",
  "demo.hideScript": "Masquer le script R",

  "method.wilson": "Intervalle de Wilson (prop.test, sans correction de continuité)",
  "method.survey_logit": "Proportion pondérée, plan d'enquête (survey::svyciprop, méthode logit)",

  "errors.r_not_found": "R est introuvable. Vérifiez l'installation de SuiviEvalLab.",
  "errors.r_incomplete": "Le moteur R est incomplet. Réinstallez SuiviEvalLab.",
  "errors.r_start_timeout": "R n'a pas démarré à temps. Réessayez dans quelques secondes.",
  "errors.r_bad_start": "R a renvoyé un message de démarrage inattendu.",
  "errors.r_timeout": "Le calcul R a dépassé le délai autorisé.",
  "errors.r_stopped": "Le moteur R s'est arrêté pendant le calcul. Réessayez.",
  "errors.r_desync": "Réponse du moteur R désynchronisée. Réessayez.",
  "errors.r_error": "Erreur dans le calcul R : {detail}",
  "errors.invalid_design": "Type de calcul inconnu.",
  "errors.engine_unavailable": "Le moteur de calcul n'est pas disponible.",
  "errors.engine_stopped": "Le moteur de calcul s'est arrêté. Il redémarre automatiquement.",
  "errors.timeout": "L'opération a dépassé le délai autorisé.",
  "errors.not_allowed": "Action non autorisée.",
  "errors.unknown": "Une erreur inattendue s'est produite : {detail}",
};

export type MessageKey = keyof typeof fr;

export const en: Record<MessageKey, string> = {
  "app.preview": "Preview, simulated engines",
  "app.offline": "Offline",

  "nav.label": "Navigation",
  "nav.project": "Project",
  "nav.steps": "Project steps",
  "nav.start": "Start",
  "nav.overview": "Overview",
  "nav.framework": "Results framework",
  "nav.indicators": "Indicators",
  "nav.data": "Data",
  "nav.report": "Report",
  "nav.soon": "Available in a future version",

  "side.fold": "Collapse the sidebar",
  "side.version": "Version {version}",
  "side.theme": "Switch theme",
  "side.language": "Interface language",

  "start.title": "Start",
  "start.lead":
    "This first version checks that the app and its two calculation engines work on your computer, without an internet connection.",

  "engines.title": "Calculation engines",
  "engines.recheck": "Check again",
  "engines.ui": "Interface",
  "engines.python": "Python engine",
  "engines.r": "R statistical engine",
  "engines.pythonDetail": "Python {python}, polars {polars}, engine {engine}",
  "engines.rDetail": "R {r}, survey {survey}, nanoarrow {nanoarrow}",
  "engines.missing": "missing",
  "engines.starting": "Starting",
  "engines.rStarting": "Starting, a few seconds",
  "engines.unavailable": "Unavailable",
  "engines.logs": "Engine log: {path}",

  "status.readyFeminine": "Ready",
  "status.ready": "Ready",
  "status.error": "Error",
  "status.waiting": "Waiting",

  "demo.title": "Demo calculation",
  "demo.lead":
    "Share of girls aged 6 to 11 attending school, over 612 fictional households. The calculation runs in R, as every calculation in the app will.",
  "demo.designLabel": "Calculation type",
  "demo.survey": "With survey design",
  "demo.simple": "Simple sample",
  "demo.run": "Run the calculation",
  "demo.running": "Calculating",
  "demo.failed": "The calculation failed",
  "demo.ci": "{level} confidence interval: {low} to {high}",
  "demo.counts": "{x} of {n} girls attend school.",
  "demo.showScript": "Show the R script",
  "demo.hideScript": "Hide the R script",

  "method.wilson": "Wilson interval (prop.test, no continuity correction)",
  "method.survey_logit": "Weighted proportion, survey design (survey::svyciprop, logit method)",

  "errors.r_not_found": "R cannot be found. Check the SuiviEvalLab installation.",
  "errors.r_incomplete": "The R engine is incomplete. Reinstall SuiviEvalLab.",
  "errors.r_start_timeout": "R did not start in time. Try again in a few seconds.",
  "errors.r_bad_start": "R returned an unexpected start message.",
  "errors.r_timeout": "The R calculation took too long.",
  "errors.r_stopped": "The R engine stopped during the calculation. Try again.",
  "errors.r_desync": "The R engine response was out of sync. Try again.",
  "errors.r_error": "Error in the R calculation: {detail}",
  "errors.invalid_design": "Unknown calculation type.",
  "errors.engine_unavailable": "The calculation engine is not available.",
  "errors.engine_stopped": "The calculation engine stopped. It restarts automatically.",
  "errors.timeout": "The operation took too long.",
  "errors.not_allowed": "Action not allowed.",
  "errors.unknown": "An unexpected error occurred: {detail}",
};
