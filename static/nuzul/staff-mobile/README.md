# Staff Mobile — تطبيق الموظفين

Mobile app for housekeeping (التدبير) and maintenance (الصيانة) staff. Two example screens.

## Screens

- **TaskListScreen** — greeting + progress ring + tabs (المهام / المخزون / رسائل) + room cards with status colors (in-progress / ready / blocked / done) and VIP markers.
- **TaskDetailScreen** — checklist of sub-tasks, guest notes in a gold-bordered card, sticky footer with primary/secondary actions.

## Device frame

Both screens are rendered inside the `IOSDevice` starter component (`ios-frame.jsx`). Width is 390 px to match iPhone 14/15.

## Why two screens

The brief specifies a staff mobile app for **housekeeping and maintenance**. Show staff their queue + let them drill into a single task. Wire up the checklist items to your task-completion API.
