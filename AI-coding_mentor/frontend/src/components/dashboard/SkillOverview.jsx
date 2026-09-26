import { BrainCircuit, ShieldCheck, Sparkles } from 'lucide-react';
import { Panel } from './Panel';

const tierClass = (value = '') => value.toLowerCase().includes('advanced') ? 'tier-advanced' : value.toLowerCase().includes('intermediate') ? 'tier-intermediate' : 'tier-beginner';
const label = (value = '') => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function SkillOverview({ profile, profileLoading, profileError, retryProfile, assessment, assessmentLoading, assessmentError, retryAssessment }) {
  const topics = profile?.topics || [];
  const predictedTopics = topics.filter((topic) => topic.predicted_skill);
  const strong = assessment?.strong_topics || [];
  const weak = assessment?.weak_topics || [];
  const developing = topics.filter((topic) => topic.rule_based_skill?.toLowerCase().includes('beginner')).map((topic) => topic.topic).filter((topic) => !weak.includes(topic));
  const needsPractice = (!profile && !assessment && !profileError && !assessmentError) || [profileError?.status, assessmentError?.status].some((status) => [400, 404, 422].includes(status));
  const empty = needsPractice && <><BrainCircuit size={24} /><strong>Your skill profile starts with practice</strong><span>Complete an assessment or a few coding activities to build your profile.</span><a className="text-button" href="/assessment">Take an assessment <span aria-hidden="true">→</span></a></>;
  return <Panel title="Skill snapshot" subtitle="A view of what you know and what you can grow" className="skill-panel" loading={profileLoading && assessmentLoading} error={null} onRetry={() => { retryProfile(); retryAssessment(); }} empty={empty}>
    <div className="skill-sources">
      <div className="skill-source-card rule-source">
        <div className="skill-source-heading"><span className="source-icon rule-icon"><ShieldCheck size={16} /></span><span>ASSESSMENT PROFILE</span></div>
        {assessmentLoading ? <div className="inline-skeleton" /> : assessmentError ? <p className="muted-copy">Assessment profile unavailable.</p> : assessment ? <>
          <div className="rule-level-row"><strong className={tierClass(assessment.skill_level)}>{label(assessment.skill_level)}</strong><span>{assessment.overall_score}% score</span></div>
          <div className="topic-groups">
            <TopicGroup title="Strong" values={strong.slice(0, 3)} variant="strong" />
            <TopicGroup title="Developing" values={(developing.length ? developing : weak).slice(0, 3)} variant="developing" />
          </div>
        </> : <p className="muted-copy">Complete a coding assessment to see your rule-based level and strong topics.</p>}
      </div>
      <div className="skill-source-card ml-source">
        <div className="skill-source-heading"><span className="source-icon ml-icon"><Sparkles size={16} /></span><span>ML SKILL ESTIMATE</span><span className="estimate-tag">PREDICTED</span></div>
        {profileLoading ? <div className="inline-skeleton" /> : profileError || profile?.status !== 'ready' ? <div className="ml-empty"><span>ML skill prediction unavailable</span><small>{profile?.message || 'Complete more coding activities to build a useful prediction.'}</small></div> : <>
          <p className="estimate-disclaimer">A model estimate, not a guaranteed measure of ability.</p>
          <div className="skill-bars">
            {predictedTopics.slice(0, 4).map((topic) => <div className="skill-bar-row" key={topic.topic}>
              <span>{label(topic.topic)}</span><div className="skill-bar" role="img" aria-label={`${label(topic.topic)} prediction confidence ${Math.round((topic.confidence ?? 0) * 100)} percent`}><i className={tierClass(topic.predicted_skill)} style={{ width: `${Math.max(3, Math.min(100, (topic.confidence ?? 0) * 100))}%` }} /></div><b>{label(topic.predicted_skill)} <small>{Math.round((topic.confidence ?? 0) * 100)}%</small></b>
            </div>)}
          </div>
          {!predictedTopics.length && <p className="muted-copy">Complete more coding activities to generate topic estimates.</p>}
        </>}
      </div>
    </div>
  </Panel>;
}

function TopicGroup({ title, values, variant }) {
  return <div className={`topic-group ${variant}`}><span>{title}</span>{values.length ? <div className="topic-chips">{values.map((value) => <i key={value}>{label(value)}</i>)}</div> : <small>Not enough data yet</small>}</div>;
}
