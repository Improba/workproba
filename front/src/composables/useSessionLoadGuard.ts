/** Garde-fou contre les courses lors de changements rapides de session. */
export function createSessionLoadGuard() {
  let generation = 0;

  return {
    /** Démarre un nouveau chargement et renvoie son identifiant de génération. */
    next(): number {
      generation += 1;
      return generation;
    },
    /** true si une charge plus récente a été lancée depuis `requested`. */
    isStale(requested: number): boolean {
      return requested !== generation;
    },
  };
}
