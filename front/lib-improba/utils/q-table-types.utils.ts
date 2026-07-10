import type { QTable } from 'quasar';

import type { ItemOfArray } from './type-aliases.utils';

type ObjectWithOptionalProps = Pick<QTable, 'columns' | 'pagination'>;

type ObjectWithRequiredProps = Required<ObjectWithOptionalProps>;

type QTableColumns = ObjectWithRequiredProps['columns'];

export type QTableColumn = ItemOfArray<QTableColumns>;

export type QTablePagination = ObjectWithRequiredProps['pagination'];
