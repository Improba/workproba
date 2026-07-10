import * as generalComponents from 'src/../lib-improba/components';
import * as mastokComponents from 'src/../lib-improba/components/mastok';
import { App } from 'vue';

export const boot = (options: { app: App<any> }) => {
  // ***********
  // Improba components
  // ***********

  console.log(`Registering ${Object.keys(generalComponents)?.length} Improba components...`);
  // Loop on each "general" component to register it as global
  // for (const compoName in generalComponents) {
  //   options.app.component(compoName, (<any>generalComponents)[compoName]);
  // }
  for (const compoName in mastokComponents) {
    options.app.component(compoName, (<any>generalComponents)[compoName]);
  }
  console.log('Registering Improba components done.');
  // ***********
};
