import * as fs from 'fs';
import * as Excel from 'exceljs';
import { Row, Worksheet } from 'exceljs';
import { Workbook } from 'exceljs';

/*

{
  type: 'excel',
  fileName: 'toto'
  worksheets: [
    {
      name: 'Sheet1',
      columns: [
        {
          header: 't-number',
          width: 20,
          key: 't'
        },
        {
          header: 't-name',
          width: 40,
          key: 't2'
        }
      ],
      rows: [
        {
          t: 45,
          t2: 'toto'
        }
      ]
    }
  ]
}

*/

export interface IWorksheet {
  name: string;
  columns: {
    header: string;
    key: string;
    width: number;
  }[];
  rows: {
    [key: string]: any;
  }[];
}

export const exportData = async (options: {
  type: 'csv' | 'excel';
  filePath: string;
  worksheets: IWorksheet[];
}) => {
  const workbook = new Workbook();
  for (const worksheet of options.worksheets) {
    const ws = workbook.addWorksheet(worksheet.name);

    ws.columns = worksheet.columns;

    // Loop on each line to insert it in the worksheet (ws)
    for (const row of worksheet.rows) {
      // This is the row we will add
      const rowToBeInserter: any[] = [];

      // Loop on each column
      for (const col of ws.columns) {
        let valueToBeInserted: any;
        if (typeof col.key === 'string') {
          // dosimeter.name : We should use col[dosimeter][name]
          const keyStrArray = col.key.split('.');
          let val: any = row;
          for (const k of keyStrArray) {
            val = val[k];
          }
          valueToBeInserted = val;
          // rowToBeInserter.push(val)
        } else if (typeof col.key === 'function') {
          // rowToBeInserter.push((<any>col.key)(row))
          valueToBeInserted = (<any>col.key)(row);
        }

        // Convert to utf8 string
        rowToBeInserter.push(JSON.parse(JSON.stringify(valueToBeInserted)));
      }
      ws.addRow(rowToBeInserter);
    }
  }

  let filePath = options.filePath;

  if (options.type === 'excel') {
    if (!filePath.endsWith('.xlsx')) filePath += '.xlsx';
    await workbook.xlsx.writeFile(filePath);
  } else {
    if (!filePath.endsWith('.csv')) filePath += '.csv';
    await workbook.csv.writeFile(filePath);
  }
};
