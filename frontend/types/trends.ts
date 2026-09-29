/** Public trends transport aliases; product limits remain backend-owned. */
export type {
  ExtendedDigestCadence as DigestCadence,
  ExtendedFollowedTopicVM as FollowedTopicVM,
  ExtendedFollowListVM as FollowListVM,
  ExtendedDigestSettingsVM as DigestSettingsVM,
  ExtendedUnsubscribeResultVM as UnsubscribeResultVM,
} from './wire/dtos';

export const MAX_FOLLOWED_TOPICS = 10;
export const MAX_TOPIC_LENGTH = 120;
