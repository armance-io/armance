---
version: 1.0.0
name: Armance UI Design System
colors:
  light:
    bg-paper: "#f4ede0"
    bg-paper-deep: "#e8dfcd"
    bg-paper-card: "#faf6ef"
    ink: "#2a2520"
    ink-soft: "#5b5145"
    ink-faint: "#9c8e7e"
    rule: "#d6c8ad"
    rule-soft: "#e8dfcd"
    accent: "#6b4f8a"
    accent-soft: "#b7a4c9"
    accent-deep: "#4a3666"
    danger: "#a44141"
    warning: "#b08a3a"
  dark:
    bg-paper: "#1d1a17"
    bg-paper-deep: "#15120f"
    bg-paper-card: "#231f1b"
    ink: "#e9e0cd"
    ink-soft: "#b3a895"
    ink-faint: "#6e6152"
    rule: "#3a3328"
    rule-soft: "#2a2520"
    accent: "#b7a4c9"
    accent-soft: "#6b4f8a"
    accent-deep: "#d6c8ad"
    danger: "#c95a5a"
    warning: "#cf9c77"
typography:
  display:
    fontFamily: "Instrument Serif, Cormorant Garamond, Georgia, serif"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
  code:
    fontFamily: "JetBrains Mono, Menlo, monospace"
shapes:
  cards: "carrées (sharp square corners, border-radius 2px or none for content containers)"
  portraits: "ronds qui s'inclinent (circular borders with mouse-over rotation -2deg to 2deg)"
  buttons: "violets (violet background for confirmations, ghost/parchment for cancel)"
---

# Spécification Design · Armance

Ce document formalise la charte graphique et l'identité visuelle d'**Armance**, inspirée par l'atmosphère des ateliers littéraires et d'archivage de la **Belle Époque**. 

---

## 1. Overview
L'univers visuel d'Armance s'inspire du charme feutré des ateliers d'imprimerie et de recherche de la fin du XIXe siècle. Il privilégie des textures douces, des couleurs chaudes évoquant le papier chiffon, un encrage modéré, et un accent violet profond représentant la teinte singulière du regard des agents.
Le design rejette les aplats agressifs et les couleurs primaires modernes pour susciter une sensation de calme, de rigueur académique et de soin artisanal.

---

## 2. Colors

La palette chromatique est rigoureusement contrainte. Aucun émoji coloré de base (comme 🟢, 🔴, 🟡) ou couleur primaire saturée n'est toléré pour les états fonctionnels : ils sont remplacés par des **gemmes HSL** douces assorties aux teintes générales.

### Mode Clair (Parchemin default)
- **Papier principal (`--bg-paper`)** : `#f4ede0` (Teinte de fond parchemin chaud)
- **Papier profond (`--bg-paper-deep`)** : `#e8dfcd` (Zones sombres, sidebar)
- **Papier carte (`--bg-paper-card`)** : `#faf6ef` (Fonds de cartes clairs)
- **Encre principale (`--ink`)** : `#2a2520` (Brun-noir doux et reposant pour la lecture)
- **Encre douce (`--ink-soft`)** : `#5b5145` (Textes secondaires, notes)
- **Règle (`--rule`)** : `#d6c8ad` (Bordures de composants, séparateurs)
- **Accent Violet (`--accent`)** : `#6b4f8a` (Violet Mona - yeux du personnel, liens, boutons principaux)
- **Accent Doux (`--accent-soft`)** : `#b7a4c9` (Remplissages légers, bordures secondaires)
- **Accent Profond (`--accent-deep`)** : `#4a3666` (Raisonnement actif)
- **États Doux (HSL)** :
  - *Succès/Normal* : `hsl(120, 15%, 55%)` (Vert sauge doux)
  - *Alerte/Erreur* : `hsl(0, 30%, 65%)` (Rouge terre cuite)
  - *Attention* : `hsl(35, 30%, 60%)` (Orange ocre)

---

## 3. Typography

Trois familles de polices de caractères complémentaires sont utilisées :
1. **Instrument Serif (`--ff-serif`)** : Réservée exclusivement aux grands titres d'affichage (H1, H2, citations littéraires). Utilisée fréquemment en italique pour asseoir le ton d'époque.
2. **Inter (`--ff-sans`)** : La police de référence pour **TOUS** les éléments d'interface utilisateur fonctionnels (boutons, formulaires, cartes, grilles de suivi, labels, dialogues). Elle garantit une lisibilité parfaite et uniforme.
3. **JetBrains Mono (`--ff-mono`)** : Réservée aux blocs de code, identifiants techniques (ex. IDs de runs ou tokens), durées, logs et mesures quantitatives.

---

## 4. Shapes & Geometry

- **Combos "carrées"** : Les cartes de contenu, blocs de code, tiroirs de saisie et formulaires adoptent des angles droits et affirmés (bordures fines, coins nets à 2px d'arrondi ou carrés parfaits). Cela renforce l'aspect rigide d'un classeur ou d'une fiche d'archive cartonnée.
- **Portraits ronds qui s'inclinent** : Les portraits d'agents sont toujours insérés dans un ovale parfait ou un cercle (`border-radius: 999px`) épinglé d'une fine bordure. Au survol de la souris (`:hover`), le portrait s'anime délicatement en s'inclinant (`transform: rotate(2deg) translateY(-3px)`) pour donner une sensation organique de mouvement.

---

## 5. Components Common Patterns

### Boutons Violets (`.ae-save-btn`)
Les boutons d'action primaire et de validation utilisent toujours un fond violet uni (`--accent`) et des lettres blanches, avec un passage au violet profond (`--accent-deep`) au survol.

### Boutons Fantômes / Beiges (`.dr-dl-btn`)
Les boutons d'action secondaire, d'annulation ou de téléchargement adoptent un fond transparent, une bordure fine couleur règle (`--rule`) et passent au violet ou beige doux au survol.

### Fleurons (❦)
Le symbole du fleuron (`❦`) est utilisé comme séparateur de section majeur. Il est stylisé en violet doux, flanqué de deux fines bordures latérales horizontales qui s'estompent.

---

## 6. Do's and Don'ts

### À Faire (Do)
- Utiliser **Inter** comme unique police de référence pour tous les boutons, entrées et étiquettes de contrôle.
- Utiliser les classes globales de confirmation modale pour tous les dialogues critiques de sauvegarde ou de suppression.
- Assurer un effet de transition fluide lors des copies de blocs de code ou d'images.
- Conserver des pastilles de statut extrêmement douces et cohérentes avec le papier.

### À Éviter (Don't)
- **Jamais** d'émojis criards modernes dans la copie visible ou les statuts, sauf cas fonctionnel imposé par les gems doux.
- **Jamais** d'exclamation dans le contenu rédigé pour préserver un ton de recherche noble et posé.
- **Jamais** de fenêtres d'alerte natives du navigateur (`alert()` ou `confirm()`), jugées indignes de l'esthétique soignée de l'Atelier.

---

## 7. Development & Aesthetics Verification

To ensure that the visual aesthetics remain premium and robust across updates:

### Dev Commands
Run inside `web/frontend/`:
- **Local Dev Server**: `pnpm dev` starts the server on `http://localhost:3000`.
- **Type Checking**: `pnpm typecheck` (`tsc --noEmit`) to verify all React and TypeScript typings.
- **Lint Check**: `pnpm lint` to ensure strict coding styles and prevent hardcoded string leakage.
- **Unit Testing**: `pnpm test` triggers fast modular component testing via Vitest and Testing Library.
- **E2E Visual Tests**: `pnpm playwright test` validates visual-regression rendering and full user flows against expected layout baselines under both `parchment` light mode and dark mode.

