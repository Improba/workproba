import { Notify } from 'quasar';

export const notify = (options: { message: string; color?: string }) => {
  Notify.create({
    message: options.message,
    color: options.color ?? 'accent-medium',
  });
};
