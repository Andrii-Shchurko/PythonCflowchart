#include <stdio.h>

int main() {
    int i;
    int sum = 0;
    int number;

    printf("Введіть 10 чисел: ");

    for (i = 0; i < 10; i++) {
        printf("Введіть число: ", i + 1);
        scanf("%d", &number);
        sum += number;
    }

    printf("Сума введених чисел: ", sum);

    return 0;
}
