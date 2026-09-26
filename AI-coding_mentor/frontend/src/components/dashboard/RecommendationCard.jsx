import { ArrowUpRight, Braces, CircleHelp, Gauge } from 'lucide-react';

const difficultyClass = (difficulty = '') => `difficulty-${difficulty.toLowerCase()}`;
const titleCase = (value = '') => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function RecommendationCard({ item, index = 0 }) {
  return <article className="recommendation-card" style={{ '--card-delay': `${index * 70}ms` }}>
    <div className="rec-card-top"><span className="rec-topic-icon"><Braces size={16} /></span><span className={`difficulty-pill ${difficultyClass(item.difficulty)}`}><i />{titleCase(item.difficulty)}</span></div>
    <h3>{item.title}</h3>
    <div className="rec-topic"><span>{titleCase(item.topic)}</span><span className="rec-score"><Gauge size={13} /> {item.score}</span></div>
    <p className="rec-reason"><CircleHelp size={14} />{item.reason}</p>
    <a className="rec-action" href={`/questions/${encodeURIComponent(item.question_id)}`} aria-label={`Start ${item.title}`}>Start challenge <ArrowUpRight size={15} /></a>
  </article>;
}
