/** Public plan transport aliases; quota enforcement remains backend-owned. */
import type { ExtendedPlanQuotasVM as PlanQuotasVM } from './wire/dtos';
export type {
  ExtendedPlanTier as PlanTier,
  ExtendedPlanQuotasVM as PlanQuotasVM,
  ExtendedMyPlanVM as MyPlanVM,
} from './wire/dtos';

export const FREE_PLAN_QUOTAS: PlanQuotasVM = { evidenceDaily: 30, noveltyDaily: 5 };
