import { Workbook } from 'exceljs';
import { saveAs } from 'file-saver';
import { createDialog } from 'src/../lib-improba/utils/dialog.utils';
import DExportCustomCompoForDialog from 'src/../lib-improba/components/utils/DExportCustomCompoForDialog.vue';

// ****************
// Use cases
// ****************

/*
await createFile(
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
        )
*/

// ****************
// Export code
// ****************

export interface IWorksheet {
  name: string;
  columns: {
    header: string;
    key: string | ((row: any) => any);
    width: number;
  }[];
  rows: {
    [key: string]: any;
  }[];
}

export const exportDataWithDialog = async (options: {
  worksheets: IWorksheet[];
}) => {
  const dialogRes = await createDialog({
    component: DExportCustomCompoForDialog,
    componentProps: {},
    persistent: true,
  });

  if (dialogRes === false) return;

  await exportData({
    type: dialogRes.type,
    fileName: dialogRes.name,
    worksheets: options.worksheets,
  });
};

export const exportData = async (options: {
  type: 'csv' | 'excel';
  fileName: string;
  worksheets: IWorksheet[];
}) => {
  const workbook = new Workbook();
  for (const worksheet of options.worksheets) {
    const ws = workbook.addWorksheet(worksheet.name);

    ws.columns = worksheet.columns.map(
      (col: {
        header: string;
        key: string | ((row: any) => any);
        width: number;
      }) => {
        return {
          ...col,
          key: typeof col.key === 'string' ? col.key : undefined,
        };
      }
    );

    // Loop on each line to insert it in the worksheet (ws)
    for (const row of worksheet.rows) {
      // This is the row we will add
      const rowToBeInserter: any[] = [];

      // Loop on each column
      for (const col of worksheet.columns) {
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

  if (options.type === 'excel') {
    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    saveAs(blob, `${options.fileName}.xlsx`);
  } else {
    const buffer = await workbook.csv.writeBuffer();
    const blob = new Blob([buffer], {
      type: 'text/plain',
    });
    saveAs(blob, `${options.fileName}.csv`);
  }
};
