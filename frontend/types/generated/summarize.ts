/** Generated wire aliases and explicit refinements enforced by classifySummarizeResponse. */
import type {
  SummarizationSummaryResultDTO, SummarizationSummaryDraft, SummarizationTranslationDraft,
  SummarizationSummarizeScope, SummarizationResponse,
  ExtendedSummarizeValidationErrorDTO, ExtendedUnauthorizedDTO,
} from '../wire/dtos';

export type {
  SummarizationSummarizeTask as SummarizeTask,
  SummarizationSummarizeScope as SummarizeScope,
  SummarizationPersona as Persona,
  SummarizationSummaryRequest as SummarizeRequest,
  SummarizationAnchor as AnchorVM,
  SummarizationReproducibility as ReproducibilityVM,
  SummarizationSummaryDraft as SummaryVM,
  SummarizationTranslationDraft as TranslationVM,
  SummarizationSummaryMeta as SummaryMeta,
  SummarizationPendingDTO as SummaryPendingDTO,
  SummarizationAbstainDTO as SummaryAbstainDTO,
  SummarizationCostDegradedDTO as CostDegradedDTO,
  SummarizationSourceUnavailableDTO as SourceUnavailableDTO,
  SummarizationAssetRef as AssetRef,
  SummarizationAssetsOkDTO as AssetsOkDTO,
  SummarizationAssetsLicenseUnavailableDTO as AssetsLicenseUnavailableDTO,
  SummarizationAssetsUnauthorizedDTO as UnauthorizedDTO,
  SummarizationPaperAssetsResponse as PaperAssetsResponseDTO,
} from '../wire/dtos';

export type StandardGlossaryItem = NonNullable<SummarizationTranslationDraft['standardGlossary']>[number];
export type SummaryOkDTO = Omit<SummarizationSummaryResultDTO, 'task' | 'summary'> & {
  task: 'summary'; summary: SummarizationSummaryDraft;
};
export type TranslationOkDTO = Omit<SummarizationSummaryResultDTO, 'task' | 'translation'> & {
  task: 'translate'; translation: SummarizationTranslationDraft; scope?: SummarizationSummarizeScope;
};
// HTTP error envelopes are produced by the router rather than the domain response schema.
export type SummarizeValidationErrorDTO = ExtendedSummarizeValidationErrorDTO;
export type SummarizeResponseDTO = Exclude<SummarizationResponse, SummarizationSummaryResultDTO> |
  SummaryOkDTO | TranslationOkDTO | SummarizeValidationErrorDTO | ExtendedUnauthorizedDTO;
