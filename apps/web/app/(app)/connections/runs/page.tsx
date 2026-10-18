import { redirect } from "next/navigation";

// Runs are listed on the Connections page; this keeps the breadcrumb link working.
export default function RunsIndex() {
  redirect("/connections?tab=runs");
}
