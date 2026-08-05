from src.polybot.config import get_settings


def main():
    print(get_settings().env)


if __name__ == "__main__":
    main()
