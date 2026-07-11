"use client";

import { motion } from "framer-motion";
import type { Transaction } from "@/lib/types";

interface TransactionListProps {
  transactions: Transaction[];
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString("en-BD", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

const STATUS_CLASS: Record<string, string> = {
  completed: "text-success",
  pending: "text-warning",
  failed: "text-danger",
};

const TYPE_LABEL: Record<string, string> = {
  cash_out: "Cash Out",
  cash_in: "Cash In",
};

export function TransactionList({ transactions }: TransactionListProps) {
  if (transactions.length === 0) {
    return (
      <p className="text-body-sm text-tertiary px-4 py-6 text-center">
        No recent transactions.
      </p>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-default">
      {transactions.map((txn, i) => (
        <motion.div
          key={txn.id}
          className="flex items-start justify-between gap-3 px-4 py-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2, delay: i * 0.04 }}
        >
          <div className="min-w-0">
            <p className="text-title-sm text-primary">
              {TYPE_LABEL[txn.txn_type] ?? txn.txn_type}
            </p>
            <p className="text-body-sm text-tertiary truncate">
              {txn.account_id} · {fmtTime(txn.ts)}
            </p>
            {txn.event_flag && (
              <p className="text-label-sm text-brand mt-0.5">{txn.event_flag}</p>
            )}
          </div>
          <div className="text-right shrink-0">
            <p className="text-title-md tabular-nums-bv text-primary">
              ৳{fmt(txn.amount)}
            </p>
            <p className={`text-label-sm ${STATUS_CLASS[txn.status] ?? "text-tertiary"}`}>
              {txn.status}
            </p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
