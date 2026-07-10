<!--
  Composant MPage - Page Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-page de Quasar qui applique le style Mastok
  et utilise le système de couleurs Anubis. Il remplace DPage avec un style cohérent
  avec les autres composants Mastok.
  
  Différences par rapport à q-page de Quasar :
  
  1. Système de couleurs Anubis :
     - Utilise bg-neutral-lowest pour le fond (au lieu des couleurs Quasar par défaut)
     - Utilise text-text pour la couleur de texte (s'adapte automatiquement au mode clair/sombre)
     - Garantit une cohérence visuelle avec le reste de l'application
  
  2. Transitions Mastok :
     - Ajoute la classe smooth pour des transitions fluides et cohérentes
     - Suit les standards de timing définis dans le système Mastok
  
  3. Gestion du scroll améliorée :
     - Structure avec overflow: auto pour un scroll contrôlé
     - Layout flex optimisé pour garantir un affichage correct sur tous les écrans
     - Évite les problèmes de scroll indésirables
  
  4. Padding optionnel :
     - Prop padding pour ajouter facilement un espacement interne (q-pa-md)
     - Plus flexible que de devoir ajouter manuellement les classes Quasar
  
  5. Structure de layout robuste :
     - Structure flex imbriquée garantissant que le contenu prend toute la hauteur disponible
     - Évite les problèmes de layout courants avec q-page seul
     - Permet l'utilisation de la classe "fit" dans le slot pour créer des conteneurs plein écran
  
  Structure technique importante :
  - q-page avec "col column" : prend toute la hauteur disponible et crée un contexte flex vertical
  - Div wrapper avec "col fit column" : crée un contexte de positionnement relatif nécessaire pour "fit"
  - Structure flex imbriquée : garantit que le slot peut utiliser "fit" correctement
  ⚠️ NE PAS SIMPLIFIER cette structure, elle est nécessaire pour que "fit" fonctionne !
  
  Avantages par rapport à q-page :
  - Cohérence visuelle avec le système de design Anubis/Mastok
  - Support automatique du mode clair/sombre via les couleurs Anubis
  - Configuration simplifiée (padding en prop plutôt qu'en classe)
  - Structure de layout plus robuste et prévisible
  - Intégration transparente avec les autres composants Mastok
  
  Props :
  - padding : Ajoute un padding (q-pa-md) si activé (défaut: false)
  
  Utilisation :
  
  Page simple :
  ```vue
  <MPage>
    <div>Contenu de la page</div>
  </MPage>
  ```
  
  Page avec padding :
  ```vue
  <MPage :padding="true">
    <div>Contenu avec espacement interne</div>
  </MPage>
  ```
  
  Page avec conteneur fit (prend toute la hauteur et peut scroller) :
  ```vue
  &lt;MPage&gt;
    &lt;div class="fit column"&gt;
      Ce div prendra toute la hauteur disponible grâce à la structure interne de MPage
      Le scroll se fera automatiquement si le contenu dépasse
    &lt;/div&gt;
  &lt;/MPage&gt;
  ```
  
  Note : Ce composant remplace DPage et doit être utilisé dans les nouveaux développements.
  Pour migrer depuis q-page, remplacez simplement &lt;q-page&gt; par &lt;MPage&gt;.
  
  ⚠️ IMPORTANT : La structure interne de MPage est nécessaire pour que la classe "fit" 
  fonctionne correctement dans le slot. Ne pas simplifier cette structure !
-->
<template>
  <!-- 
    q-page avec col column : 
    - col : prend toute la hauteur disponible dans le q-page-container
    - column : direction flex verticale pour permettre aux enfants de s'empiler verticalement
    Cette structure est nécessaire pour que la classe "fit" fonctionne correctement dans le slot.
  -->
  <q-page class="col column bg-neutral-lowest text-text smooth">
    <!-- 
      Div wrapper avec col fit column :
      - col : prend toute la hauteur du q-page parent
      - fit : position absolute (top/right/bottom/left: 0) pour occuper tout l'espace disponible
      - column : direction flex verticale pour le contenu
      - overflow: auto : permet le scroll si le contenu dépasse
      
      IMPORTANT : Cette structure est nécessaire pour que les éléments avec class="fit" 
      dans le slot fonctionnent correctement. Ne pas simplifier cette structure !
    -->
    <div :class="pageClass" style="overflow: auto">
      <!-- 
        Structure flex imbriquée :
        - col : prend toute la hauteur du parent
        - display: flex; flex-wrap: wrap : permet au contenu de s'adapter correctement
        Cette structure garantit que le slot peut utiliser class="fit" pour occuper tout l'écran.
      -->
      <div class="col" style="display: flex; flex-wrap: wrap">
        <!-- 
          Conteneur final avec flex: 1 0 100% :
          - flex: 1 0 100% : prend toute la largeur disponible et peut grandir
          - C'est ici que le slot est rendu, permettant l'utilisation de class="fit"
        -->
        <div style="flex: 1 0 100%">
          <slot></slot>
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps({
  padding: {
    type: Boolean,
    default: false,
  },
});

const pageClass = computed(
  () => `col fit column ${props.padding ? 'q-pa-md' : ''}`
);
</script>

