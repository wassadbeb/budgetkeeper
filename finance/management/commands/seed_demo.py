"""Демонстрационные данные для проверки и скриншотов."""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile, User
from finance.models import AIMessage, Account, AISuggestion, Budget, Category, Operation
from finance.services import create_default_categories


class Command(BaseCommand):
    help = "Создаёт демо-пользователя, счета, категории, операции и бюджеты"

    def handle(self, *args, **options):
        admin, admin_created = User.objects.get_or_create(
            email="admin@budgetkeeper.ru",
            defaults={
                "full_name": "Администратор BudgetKeeper",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin_created:
            admin.set_password("Admin12345!")
            admin.save()

        demo, demo_created = User.objects.get_or_create(
            email="demo@budgetkeeper.ru",
            defaults={
                "full_name": "Демо Пользователь",
                "role": User.Role.USER,
                "is_active": True,
            },
        )
        if demo_created:
            demo.set_password("Demo12345!")
            demo.save()

        Profile.objects.get_or_create(
            user=demo, defaults={"phone": "+7 900 000-00-00"}
        )
        Profile.objects.get_or_create(
            user=admin, defaults={"phone": "+7 900 111-11-11"}
        )

        if not AIMessage.objects.filter(user=demo).exists():
            AIMessage.objects.create(
                user=demo,
                role=AIMessage.Role.USER,
                content="На чём можно сэкономить в этом месяце?",
            )
            AIMessage.objects.create(
                user=demo,
                role=AIMessage.Role.ASSISTANT,
                content="Вы уже израсходовали значительную часть лимита на «Кафе и рестораны». "
                "Попробуйте готовить дома пару раз в неделю — это сэкономит до 2 000 ₽.",
            )

        create_default_categories(demo)
        create_default_categories(admin)

        card, _ = Account.objects.get_or_create(
            user=demo,
            name="Карта",
            defaults={
                "account_type": Account.AccountType.CARD,
                "initial_balance": Decimal("45000.00"),
            },
        )
        cash, _ = Account.objects.get_or_create(
            user=demo,
            name="Наличные",
            defaults={
                "account_type": Account.AccountType.CASH,
                "initial_balance": Decimal("5000.00"),
            },
        )

        today = timezone.localdate()
        current_period = today.replace(day=1)
        previous_period = (current_period - timedelta(days=1)).replace(day=1)

        budgets = {
            "Продукты": "20000.00",
            "Кафе и рестораны": "8000.00",
            "Транспорт": "5000.00",
            "Развлечения": "5000.00",
            "Одежда": "6000.00",
        }
        for name, limit in budgets.items():
            category = Category.objects.get(
                user=demo, name=name, kind=Category.Kind.EXPENSE
            )
            Budget.objects.get_or_create(
                user=demo,
                category=category,
                period_start=current_period,
                defaults={"limit_amount": Decimal(limit)},
            )

        if Operation.objects.filter(user=demo).exists():
            self.stdout.write(
                self.style.WARNING("Демо-операции уже существуют, пропускаю создание.")
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Демо-доступ: demo@budgetkeeper.ru / Demo12345!; "
                    "админ: admin@budgetkeeper.ru / Admin12345!"
                )
            )
            return

        def category(name: str, kind: str) -> Category:
            return Category.objects.get(user=demo, name=name, kind=kind)

        def moment(period: date, day: int, hour: int) -> datetime:
            last_day = calendar.monthrange(period.year, period.month)[1]
            day = max(1, min(day, last_day))
            if period == current_period:
                day = min(day, today.day)
            naive = datetime.combine(period.replace(day=day), time(hour, 0))
            return timezone.make_aware(naive)

        def add(
            period: date,
            operation_type: str,
            category_name: str,
            account: Account,
            amount: str,
            description: str,
            day: int,
            hour: int = 12,
            ai: bool = False,
            confidence: str | None = None,
        ) -> Operation:
            kind = (
                Category.Kind.INCOME
                if operation_type == Operation.OperationType.INCOME
                else Category.Kind.EXPENSE
            )
            operation = Operation.objects.create(
                user=demo,
                account=account,
                category=category(category_name, kind),
                operation_type=operation_type,
                amount=Decimal(amount),
                description=description,
                occurred_at=moment(period, day, hour),
                created_by_ai=ai,
                ai_confidence=Decimal(confidence) if confidence else None,
            )
            if ai:
                AISuggestion.objects.create(
                    user=demo,
                    operation=operation,
                    input_text=description,
                    suggested_category=operation.category,
                    confidence=Decimal(confidence or "0.800"),
                    source=AISuggestion.Source.RULES,
                    accepted=True,
                )
            return operation

        income = Operation.OperationType.INCOME
        expense = Operation.OperationType.EXPENSE

        add(current_period, income, "Зарплата", card, "85000.00", "Зарплата за месяц", 5, 10)
        add(current_period, expense, "Продукты", card, "2450.00", "Продукты в Пятёрочке", 6, 19, True, "0.900")
        add(current_period, expense, "Кафе и рестораны", card, "890.00", "Завтрак в кофейне", 7, 9)
        add(current_period, expense, "Транспорт", cash, "650.00", "Метро и автобус", 8, 8)
        add(current_period, expense, "Жильё и ЖКХ", card, "32000.00", "Аренда квартиры", 10, 12)
        add(current_period, expense, "Здоровье", card, "1200.00", "Аптека, витамины", 11, 18)
        add(current_period, expense, "Развлечения", card, "1500.00", "Кино с друзьями", 12, 20)
        add(current_period, expense, "Одежда", card, "4300.00", "Кроссовки для тренировок", 13, 15)
        add(current_period, expense, "Связь и интернет", card, "900.00", "Мобильная связь МТС", 14, 11)
        add(current_period, expense, "Продукты", card, "3100.00", "Продукты в Магните", 15, 19, True, "0.850")
        add(current_period, income, "Подработка", card, "12000.00", "Оплата фриланс-проекта", 16, 14)
        add(current_period, expense, "Кафе и рестораны", card, "2200.00", "Ужин в ресторане", 17, 21)
        add(current_period, expense, "Транспорт", cash, "1200.00", "Такси до вокзала", 18, 22)
        add(current_period, expense, "Образование", card, "2500.00", "Курс на Stepik", 19, 13)
        add(current_period, expense, "Продукты", card, "2800.00", "Продукты на неделю", 20, 18, True, "0.900")
        add(current_period, expense, "Развлечения", card, "799.00", "Подписка на онлайн-кинотеатр", 21, 10)
        add(current_period, income, "Проценты и кэшбэк", card, "350.00", "Кэшбэк за месяц", 22, 12)
        add(current_period, expense, "Здоровье", card, "3500.00", "Приём стоматолога", 23, 16)
        add(current_period, expense, "Жильё и ЖКХ", card, "4200.00", "Коммунальные платежи", 24, 11)
        add(current_period, expense, "Кафе и рестораны", cash, "450.00", "Кофе с собой", 25, 9)

        add(previous_period, income, "Зарплата", card, "82000.00", "Зарплата за прошлый месяц", 5, 10)
        add(previous_period, expense, "Жильё и ЖКХ", card, "32000.00", "Аренда квартиры", 10, 12)
        add(previous_period, expense, "Продукты", card, "5600.00", "Продукты на неделю", 12, 19, True, "0.850")
        add(previous_period, expense, "Транспорт", cash, "1400.00", "Проездной на месяц", 3, 8)
        add(previous_period, expense, "Кафе и рестораны", card, "3600.00", "Кафе и доставка еды", 18, 20)
        add(previous_period, expense, "Развлечения", card, "2100.00", "Концерт", 22, 19)
        add(previous_period, expense, "Здоровье", card, "1800.00", "Аптека", 15, 17)
        add(previous_period, expense, "Одежда", card, "5200.00", "Зимняя куртка", 25, 14)
        add(previous_period, income, "Подработка", card, "8000.00", "Разовый заказ", 27, 16)
        add(previous_period, expense, "Связь и интернет", card, "900.00", "Интернет и связь", 14, 11)

        self.stdout.write(
            self.style.SUCCESS(
                f"Создано демо-операций: {Operation.objects.filter(user=demo).count()}. "
                "Доступ: demo@budgetkeeper.ru / Demo12345!; "
                "админ: admin@budgetkeeper.ru / Admin12345!"
            )
        )
