import { PageHeader } from "../components/ui";
import { TransactionsView } from "../components/TransactionsView";

export function ExpensesPage() {
  return (
    <>
      <PageHeader
        title="Expenses"
        subtitle="Every outflow in this workspace — filter, edit and export."
      />
      <TransactionsView kind="expense" />
    </>
  );
}
