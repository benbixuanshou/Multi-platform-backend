# Per-Agent Required Output Fields

## ClassifyRouterAgent

```json
{
  "category": "question|complaint|praise|spam|neutral|ugc_gold|collab_inquiry",
  "intent": "<sub-intent per category>",
  "intent_detail": "specific sub-intent label",
  "sentiment": "positive|negative|neutral",
  "urgency": "high|medium|low",
  "needs_reply": true,
  "suggested_tone": "professional|casual|warm|humorous|no_reply",
  "key_points": ["3-5 key points"],
  "confidence": 0.0-1.0,
  "reasoning": "one sentence why"
}
```

### Intent values by category:
- question: purchase_intent, how_to_intent, comparison_intent, availability_intent, casual_question
- complaint: product_issue, service_complaint, price_complaint, platform_issue
- praise: genuine_praise, social_praise, fan_crush, low_effort_praise
- spam: ad_spam, follow_bait, bot_repetition
- neutral: off_topic, tag_others, emoji_only
- ugc_gold: detailed_experience, insightful_comment, funny_highlight
- collab_inquiry: brand_collab, pr_inquiry, platform_invite

## ReplyGenerateAgent

```json
{
  "drafts": [
    {
      "style": "warm|casual|professional",
      "content": "reply text"
    }
  ],
  "recommended": "warm|casual|professional",
  "reasoning": "why this style works best",
  "risk_warning": null  // or string describing risk
}
```

## ReplyCriticAgent

```json
{
  "evaluations": [
    {
      "style": "warm|casual|professional",
      "scores": {
        "style_match": 1-5,
        "completeness": 1-5,
        "safety": 1-5,
        "naturalness": 1-5
      },
      "specific_issues": []
    }
  ],
  "overall_recommendation": "all_good|review_recommended|needs_regeneration",
  "regeneration_hint": ""
}
```

## InsightMiningAgent

```json
{
  "overall_sentiment": {"score": 0.0-1.0, "trend": "improving|stable|declining", "summary": "..."},
  "top_topics": [{"topic": "...", "mention_count": 0, "avg_sentiment": 0.0, "example_comment": "..."}],
  "emerging_trends": [{"trend": "...", "evidence": "..."}],
  "fan_concerns": [{"concern": "...", "severity": "high|medium|low", "affected_users_count": 0}],
  "ugc_gold": [{"comment_id": "...", "username": "...", "content_preview": "...", "why_valuable": "..."}],
  "core_fans": [{"username": "...", "engagement_score": 0-100, "top_trait": "loyal|insightful|supportive"}],
  "content_suggestions": [{"suggestion": "...", "based_on": "...", "priority": "high|medium|low"}],
  "unreplied_priority": [{"comment_id": "...", "username": "...", "urgency": "high"}],
  "executive_summary": "..."
}
```

## ContentStrategyAgent

```json
{
  "next_content_ideas": [{"idea": "...", "format": "...", "platform": "...", "based_on": "...", "expected_impact": "high|medium|low", "urgency": "this_week|this_month|whenever"}],
  "community_actions": [{"action": "...", "target": "all_fans|core_fans|complaint_users|potential_customers", "based_on": "..."}],
  "business_opportunities": [{"opportunity": "...", "evidence": "...", "confidence": "high|medium|low"}],
  "risk_alerts": [{"risk": "...", "severity": "high|medium|low", "suggested_action": "..."}],
  "weekly_summary": "..."
}
```
