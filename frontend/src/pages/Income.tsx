import { PageHeader } from "../components/ui";
import { TransactionsView } from "../components/TransactionsView";

export function IncomePage() {
  return (
    <>
      <PageHeader title="Income" subtitle="Salaries, invoices and everything coming in." />
      <TransactionsView kind="income" />
    </>
  );
}
