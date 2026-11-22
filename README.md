# Branche marketmall-media

Cette branche (séparée du reste du repo) contient les médias publics et les outils de l'agent Instagram de la page @marketmall002 (« شنو واقع؟ » : les trends du Maroc expliqués en darija).

- `agent/PLAYBOOK.md` : les règles et le déroulé que l'agent suit à chaque exécution.
- `agent/render/` : rendu des carrousels (1080x1350) et des reels (1080x1920) avec texte arabe (police Cairo, licence OFL) et bande son originale synthétisée (beat + effets).
- `agent/state/log.json` : journal des posts et des actions (IDs et chiffres agrégés seulement, aucune donnée personnelle).
- `posts/` : les visuels publiés. Instagram les télécharge depuis ce repo public.

Mettre l'agent en pause : désactiver la tâche planifiée « Agent Instagram Trends » dans Claude.
