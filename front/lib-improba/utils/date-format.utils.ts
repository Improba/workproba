import { date as qDate } from 'quasar';

export function formatDate(date: Date | string, format = 'DD/MM/YYYY') {
  return qDate.formatDate(date, format);
}

export function fullDate(
  date: Date | string,
  format = 'DD-MM-YYYYTHH:mm:ss.SSSZ'
) {
  let workingDate = date;
  if (typeof date === 'string') {
    workingDate = new Date(date);
  }

  if (workingDate instanceof Date) {
    const value = qDate.formatDate(workingDate, format);
    const partDate = value.split('T')[0];
    const partTime = value.split('T')[1].split('.')[0];
    return `${partDate} à ${partTime}`;
  }
  return '-';
}

export function relativeDay(date: Date | string, uppercaseFirst = true) {
  const dateRef =
    date instanceof Date ? date : qDate.extractDate(date, 'YYYY-MM-DD');
  const today = new Date();
  const diff = qDate.getDateDiff(dateRef, today, 'days');
  let day: string;
  switch (diff) {
    case 1:
      day = 'demain';
      break;
    case 2:
      day = 'après-demain';
      break;
    case 0:
      day = "aujourd'hui";
      break;
    case -1:
      day = 'hier';
      break;
    case -2:
      day = 'avant hier';
      break;
    default:
      return formatDate(date);
  }
  return uppercaseFirst ? day.charAt(0).toUpperCase() + day.slice(1) : day;
}

export function hour(date: Date | string) {
  return formatDate(date, 'HH:mm');
}

export function relativeDayAndHour(date: Date | string, uppercaseFirst = true) {
  return relativeDay(date, uppercaseFirst) + ' à ' + formatDate(date, 'HH:mm');
}
