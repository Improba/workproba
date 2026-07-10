import { Injectable } from '@nestjs/common';
import { QuoteResponseDto } from './dto/quote-response.dto';

@Injectable()
export class QuoteService {
  private readonly subjects = [
    'Les étoiles',
    'Le vent',
    'Les nuages',
    'L\'océan',
    'Les montagnes',
    'La lune',
    'Le soleil',
    'Les arbres',
    'Les fleurs',
    'Les oiseaux',
    'Les papillons',
    'Les rêves',
    'Les pensées',
    'Les émotions',
    'Le temps',
    'L\'espace',
    'Les couleurs',
    'La musique',
    'Les mots',
    'Les souvenirs',
  ];

  private readonly verbs = [
    'dansent',
    'voyagent',
    'chuchotent',
    'respirent',
    'brillent',
    'flottent',
    'grandissent',
    's\'envolent',
    'se rencontrent',
    'se mélangent',
    's\'illuminent',
    'se transforment',
    's\'éveillent',
    's\'endorment',
    's\'unissent',
    'se séparent',
    's\'entrelacent',
    'se reflètent',
    's\'harmonisent',
    's\'élèvent',
  ];

  private readonly complements = [
    'dans un ciel infini',
    'vers l\'horizon',
    'au rythme du silence',
    'sous les rayons de l\'aube',
    'dans l\'ombre de la nuit',
    'avec grâce et légèreté',
    'dans un monde magique',
    'vers de nouveaux horizons',
    'au fil du temps',
    'dans l\'éternité',
    'sous un ciel étoilé',
    'dans la brume matinale',
    'avec les vagues',
    'dans le vent',
    'vers les sommets',
    'dans la lumière',
    'au cœur de l\'univers',
    'dans un jardin secret',
    'avec les saisons',
    'dans l\'infini',
  ];

  private readonly adjectives = [
    'magnifique',
    'mystérieux',
    'lumineux',
    'profond',
    'douce',
    'puissante',
    'éternelle',
    'fugace',
    'magique',
    'sereine',
    'vivante',
    'immense',
    'infinie',
    'douce',
    'sauvage',
    'harmonieuse',
    'mélodieuse',
    'radieuse',
    'tranquille',
    'passionnée',
  ];

  /**
   * Génère une phrase complètement aléatoire en combinant des éléments aléatoires
   * avec différentes structures de phrases
   */
  generateRandomQuote(): QuoteResponseDto {
    const structure = Math.floor(Math.random() * 4);

    let quote: string;

    switch (structure) {
      case 0:
        // Structure: Sujet + Verbe + Complément
        quote = `${this.getRandomElement(this.subjects)} ${this.getRandomElement(this.verbs)} ${this.getRandomElement(this.complements)}.`;
        break;
      case 1:
        // Structure: Sujet + Verbe + Adjectif + Complément
        quote = `${this.getRandomElement(this.subjects)} ${this.getRandomElement(this.verbs)} ${this.getRandomElement(this.adjectives)} ${this.getRandomElement(this.complements)}.`;
        break;
      case 2:
        // Structure: Adjectif + Sujet + Verbe + Complément
        quote = `${this.capitalizeFirst(this.getRandomElement(this.adjectives))} ${this.getRandomElement(this.subjects).toLowerCase()} ${this.getRandomElement(this.verbs)} ${this.getRandomElement(this.complements)}.`;
        break;
      case 3:
        // Structure: Sujet + Verbe + Adjectif
        quote = `${this.getRandomElement(this.subjects)} ${this.getRandomElement(this.verbs)} ${this.getRandomElement(this.adjectives)}.`;
        break;
      default:
        quote = `${this.getRandomElement(this.subjects)} ${this.getRandomElement(this.verbs)} ${this.getRandomElement(this.complements)}.`;
    }

    return { quote };
  }

  private getRandomElement<T>(array: T[]): T {
    return array[Math.floor(Math.random() * array.length)];
  }

  private capitalizeFirst(str: string): string {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }
}

