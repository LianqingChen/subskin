# Task Plan: Full Project Refactoring for SubSkin

## Goal
Comprehensive refactoring of the SubSkin vitiligo knowledge base project to improve code quality, architecture, and adherence to best practices using systematic development workflows.

## Current Phase
Phase 3 - Confirmed ready to execute
## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints and requirements
- [x] Document findings in findings.md
- **Status:** complete

### Phase 2: Analysis & Structure Assessment
- [x] Analyze current technical stack
- [x] Explore directory structure and main modules
- [x] Identify code quality issues and technical debt
- [x] Document findings with risk assessment
- **Status:** complete

### Phase 3: Refactoring Planning
- [x] Define refactoring approach and priorities
- [x] Create detailed refactoring plan with estimated impact
- [x] Risk assessment for each change
- [x] Get user confirmation before proceeding
- **Status:** complete

### Phase 4: Step-by-Step Refactoring
- [ ] Execute refactoring plan incrementally
- [ ] Test after each major change
- [ ] Update documentation
- **Status:** in_progress

### Phase 5: Testing & Verification
- [ ] Run linting, type checking, and tests
- [ ] Systematic engineering review using @fro.bot/systematic
- [ ] Fix any issues found
- **Status:** pending

### Phase 6: Delivery
- [ ] Final review and summary
- [ ] Update all planning documentation
- [ ] Deliver refactored project to user
- **Status:** pending

## Key Questions
1. What is the current state of the project (existing code vs new project)?
2. Are there any specific areas that need more attention than others?
3. Should we maintain backward compatibility with existing data formats?
4. What are the acceptance criteria for the refactoring?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use planning-with-files for persistent documentation | Provides external memory for large refactoring |
| Use superpowers development workflow | Systematic process reduces mistakes |
| Use @fro.bot/systematic for final review | Engineering best practices review |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       |         |            |

## Refactoring Plan by Priority

### High Priority (Low Risk, High Impact)

| Step | Changes | Risk | Impact | Notes |
|------|---------|------|--------|-------|
| 1 | **Add exports to package `__init__.py`** | Low | Medium | Currently many are empty |
| 2 | **Add missing module docstrings** | Low | Medium | Improve documentation |
| 3 | **Create `configs/.env.example`** | Low | Medium | Help new contributors get started |
| 4 | **Remove pydantic fallback in `config.py`** | Low | Medium | Pydantic is already required dependency, simplifies code |
| 5 | **Add GitHub Actions CI workflow** | Low | High | Automated testing on PR/push |
| 6 | **Fix dependency duplication - consolidate to pyproject.toml** | Medium | Medium | Remove duplication from requirements/*.txt |

### Medium Priority (Medium Risk, Medium Impact)

| Step | Changes | Risk | Impact | Notes |
|------|---------|------|--------|-------|
| 1 | **Split `config.py` into smaller modules** | Medium | High | config.py is 522 lines. Split into: `settings.py`, `logging.py`, `paths.py` |
 | 2 | **Verify `semantic_scholar_crawler.py` and add tests** | Medium | High | Already implemented, just add missing tests |
 | 3 | **Verify `clinical_trials_crawler.py` and add tests** | Medium | High | Already implemented, just add missing tests |
 | 4 | **Add tests for missing modules** | Medium | High | Improve test coverage |
 | 5 | **Create empty `__init__.py` in all subpackages** | Low | Low | Proper Python package structure |

 ### Medium Priority (新增 - Web项目审查与优化)

 | Step | Changes | Risk | Impact | Notes |
 |------|---------|------|--------|-------|
 | 6 | **分析并评审 web/ 项目** - 检查UI设计是否贴合医疗科技愿景，功能模块是否完备可用 | 低 | 高 | 用户要求重点关注社区网站开发 |
 | 7 | **根据评审结果优化改进** - 修复发现的问题，改进UI设计审美 | 中 | 高 | 使整体设计更符合医疗科技公司风格 |

 ### Low Priority (Low/Medium Risk, Future Work)

 | Step | Changes | Risk | Impact | Notes |
 |------|---------|------|--------|-------|
 | 1 | **Implement skeleton for `generators/` module** | Medium | High | Structure for weekly digest |
 | 2 | **Add more configuration files to `configs/`** | Low | Medium | crawler_config.yaml, web_config.yaml 已存在 |

## Risk Assessment Summary

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing PubMed crawler | Low | High | Existing tests cover functionality, run tests before/after |
| Changing configuration structure | Medium | Medium | Keep backward compatibility with existing .env |
| Incomplete crawler implementations | Low | Medium | Follow existing PubMed pattern |
| Dependency conflicts | Low | Medium | Verify with pip freeze after changes |

## Expected Total Changes
- ~10-15 files modified
- 2-3 new files added
- No breaking changes to existing working functionality
- All refactoring maintains backward compatibility

## Key Questions
Before proceeding, please confirm:

1. Should we **remove the requirements/*.txt files** after consolidating dependencies into pyproject.toml, or keep them for reference?
2. Do you want me to **complete the implementation of semantic_scholar_crawler and clinical_trials_crawler** (following the PubMed pattern), or just refactor the existing structure?
3. Are there any specific areas you'd like me to focus on more or less than what's outlined here?

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions (attention manipulation)
- Log ALL errors - they help avoid repetition
- Each refactoring step should be small and focused
- Test after each incremental change