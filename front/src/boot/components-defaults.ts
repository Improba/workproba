import { QInput, QInputProps, QSelect, QSelectProps } from 'quasar';
import { boot } from 'quasar/wrappers';

export default boot(() => {
  SetComponentDefaults<QInputProps>(QInput, {
    outlined: false,
    rounded: true,
    dense: false,
    stackLabel: false,
  });
  SetComponentDefaults<QSelectProps>(QSelect, {
    outlined: true,
    dense: false,
    stackLabel: true,
  });
});

/**
 * Set some default properties on a component
 */
const SetComponentDefaults = <T>(
  component: any,
  defaults: Partial<T>
): void => {
   
  Object.keys(defaults).forEach((prop: string) => {
    component.props[prop] =
      Array.isArray(component.props[prop]) === true ||
      typeof component.props[prop] === 'function'
        ? {
            type: component.props[prop],
            default: (defaults as Record<string, any>)[prop],
          }
        : {
            ...component.props[prop],
            default: (defaults as Record<string, any>)[prop],
          };
  });
   
};
