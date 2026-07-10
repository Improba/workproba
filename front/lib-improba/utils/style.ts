// selector: body.body--light // body.body--dark
const setCssVar = (name: string, value: string, selector?: string): void => {
  let item = document.body as any;
  if (selector) {
    item = document.querySelector(selector);
  }
  if (!item) {
    console.warn(`setCssVar: ${selector} not found`);
    return;
  }
  item.style.setProperty(name, value);
};

const getCssVar = (name: string, selector?: string): string => {
  let item = document.body as any;
  if (selector) {
    item = document.querySelector(selector);
  }
  if (!item) {
    console.warn(`getCssVar: ${selector} not found`);
    return '';
  }
  const value = getComputedStyle(item).getPropertyValue(name);

  return value;
};

export { setCssVar, getCssVar };
