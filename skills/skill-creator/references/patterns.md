# Skill Design Patterns
# Source: Anthropic's Complete Guide to Building Skills for Claude

## Problem-First vs Tool-First

- **Problem-first**: "I need to set up a project workspace" → Skill orchestrates the right tool calls in the right sequence; the skill handles the tools
- **Tool-first**: "I have Notion MCP connected" → Skill teaches optimal workflows and best practices; users have access, skill provides expertise

## Pattern 1: Sequential Workflow Orchestration

**Use when**: Multi-step processes in specific order.

```
## Workflow: Onboard New Customer
### Step 1: Create Account
Call MCP tool: `create_customer`
Parameters: name, email, company

### Step 2: Setup Payment
Call MCP tool: `setup_payment_method`
Wait for: payment method verification

### Step 3: Create Subscription
Call MCP tool: `create_subscription`
Parameters: plan_id, customer_id (from Step 1)
```

**Key techniques**: Explicit step ordering, dependencies between steps, validation at each stage, rollback instructions for failures.

## Pattern 2: Multi-MCP Coordination

**Use when**: Workflows span multiple services.

```
### Phase 1: Design Export (Figma MCP)
1. Export design assets
2. Generate design specifications
3. Create asset manifest

### Phase 2: Asset Storage (Drive MCP)
1. Create project folder
2. Upload all assets
3. Generate shareable links

### Phase 3: Task Creation (Linear MCP)
1. Create development tasks
2. Attach asset links to tasks
3. Assign to engineering team
```

**Key techniques**: Clear phase separation, data passing between MCPs, validation before moving to next phase, centralized error handling.

## Pattern 3: Iterative Refinement

**Use when**: Output quality improves with iteration.

```
## Iterative Report Creation
### Initial Draft
1. Fetch data via MCP
2. Generate first draft report

### Quality Check
1. Run validation script: `scripts/check_report.py`
2. Identify issues: missing sections, formatting, data errors

### Refinement Loop
1. Address each identified issue
2. Regenerate affected sections
3. Re-validate
4. Repeat until quality threshold met
```

**Key techniques**: Explicit quality criteria, iterative improvement, validation scripts, know when to stop iterating.

## Pattern 4: Context-Aware Tool Selection

**Use when**: Same outcome, different tools depending on context.

```
## Smart File Storage
### Decision Tree
1. Check file type and size
2. Determine best storage location:
   - Large files (>10MB): Use cloud storage MCP
   - Collaborative docs: Use Notion/Docs MCP
   - Code files: Use GitHub MCP
   - Temporary files: Use local storage

### Provide Context to User
Explain why that storage was chosen
```

**Key techniques**: Clear decision criteria, fallback options, transparency about choices.

## Pattern 5: Domain-Specific Intelligence

**Use when**: Skill adds specialized knowledge beyond tool access.

```
## Payment Processing with Compliance
### Before Processing (Compliance Check)
1. Fetch transaction details
2. Apply compliance rules:
   - Check sanctions lists
   - Verify jurisdiction allowances
   - Assess risk level
3. Document compliance decision

### Processing
IF compliance passed:
  - Call payment processing MCP tool
ELSE:
  - Flag for review
  - Create compliance case

### Audit Trail
- Log all compliance checks
- Record processing decisions
- Generate audit report
```

**Key techniques**: Domain expertise embedded in logic, compliance before action, comprehensive documentation, clear governance.

## Writing Best Practices

### Be Specific and Actionable
```
# Good
Run `python scripts/validate.py --input {filename}` to check data format.
If validation fails, common issues include:
- Missing required fields (add them to the CSV)
- Invalid date formats (use YYYY-MM-DD)

# Bad
Validate the data before proceeding.
```

### Include Error Handling
```
## Common Issues
### MCP Connection Failed
If you see "Connection refused":
1. Verify MCP server is running
2. Confirm API key is valid
3. Try reconnecting
```

### Reference Bundled Resources Clearly
```
Before writing queries, consult `references/api-patterns.md` for:
- Rate limiting guidance
- Pagination patterns
- Error codes and handling
```

### Combat Model "Laziness"
```
## Performance Notes
- Take your time to do this thoroughly
- Quality is more important than speed
- Do not skip validation steps
```

Note: Adding this to user prompts is more effective than in SKILL.md.

## Troubleshooting

### Skill Won't Upload
- File not named exactly `SKILL.md` (case-sensitive)
- YAML missing `---` delimiters or has unclosed quotes

### Skill Doesn't Trigger
- Description too generic
- Missing trigger phrases users would actually say
- Missing relevant file types
- Debug: Ask "When would you use the [skill name] skill?" — the agent will quote the description back

### Skill Triggers Too Often
1. Add negative triggers: "Do NOT use for X"
2. Be more specific in description
3. Clarify scope: "Use specifically for X, not for Y"

### Instructions Not Followed
1. Instructions too verbose — keep concise, use bullet points
2. Instructions buried — put critical instructions at the top
3. Ambiguous language — be specific about what to check/validate
4. Model laziness — add encouragement or use validation scripts

### Large Context Issues
- Keep SKILL.md under 5,000 words
- Move detailed docs to references/
- Consider skill "packs" for related capabilities
- Evaluate if you have >20-50 skills enabled simultaneously
