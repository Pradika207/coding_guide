import { ArrowRight, Sparkles } from 'lucide-react';
import { Panel } from './Panel';
import RecommendationCard from './RecommendationCard';

export default function Recommendations({ resource }) {
  const items = resource.data?.recommendations || [];
  const requiresAction = resource.error && [400, 404, 422].includes(resource.error.status);
  const empty = resource.data?.status === 'assessment_required' || requiresAction
    ? <><Sparkles size={23} /><strong>Personalize your practice</strong><span>Complete a coding assessment to unlock recommendations tailored to your current skills.</span><a href="/assessment" className="text-button">Start assessment <ArrowRight size={15} /></a></>
    : <><Sparkles size={23} /><strong>Your next challenge is taking shape</strong><span>Complete a few coding activities to receive personalized problem recommendations.</span></>;
  return <Panel title="Recommended for you" subtitle="Hand-picked from your learning path" className="recommendations-panel" loading={resource.loading} error={requiresAction ? null : resource.error} onRetry={resource.retry} empty={!items.length && !resource.error && !resource.loading ? empty : (!items.length && !resource.loading && (resource.data?.status === 'assessment_required' || requiresAction) ? empty : null)}>
    <div className="recommendation-grid">{items.map((item, index) => <RecommendationCard item={item} index={index} key={item.recommendation_id || item.question_id} />)}</div>
    {items.length > 0 && <a href="/questions" className="panel-footer-link">Explore question bank <ArrowRight size={15} /></a>}
  </Panel>;
}
