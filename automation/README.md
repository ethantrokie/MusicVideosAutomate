# Automation System

## Scheduled Jobs

### Daily Video Pipeline
- **Schedule:** Every day at 9:00 AM CST
- **Script:** `automation/daily_pipeline.sh`
- **Logs:** `automation/logs/daily_YYYY-MM-DD.log`

### Weekly Optimizer
- **Schedule:** Every Sunday at 10:00 AM CST
- **Script:** `automation/weekly_optimizer.py`
- **Reports:** `automation/reports/YYYY-MM-DD-analysis.md`

## Managing Jobs

Load jobs:
```bash
launchctl load ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl load ~/Library/LaunchAgents/com.learningscience.weekly.plist
```

Unload jobs:
```bash
launchctl unload ~/Library/LaunchAgents/com.learningscience.daily.plist
launchctl unload ~/Library/LaunchAgents/com.learningscience.weekly.plist
```

Check status:
```bash
launchctl list | grep learningscience
```

## Configuration

Edit `automation/config/automation_config.json` to:
- Change posting times
- Enable/disable optimization
- Change privacy status (private → public)
- Configure notifications
