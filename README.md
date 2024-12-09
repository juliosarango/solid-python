# PRINCIPIOS SOLID Y PATRONES DE DISEÑO
> Los patrones de diseño son una herramienta para diseñar programas que se pueden entender y mantener fácilmente. Los patrones de diseño son el equivalente a los planos de una ciudad mientras que los principios SOLID las leyes que lo mantienen en orden.

¿Por qué es importante usarlos?
- Son soluciones a problemas que a los largo de varias décadas se han desarrollado, entendido y se han propuesto.
- Mejora la mantenibilidad, flexibilidad y la escalabilidad del código.
- Facilita las pruebas tanto unitarias como de integración.
- Mejora el rendimiento del código
- Mejora la experiencia del desarrollador.

## Principios SOLID

### SOLID

- Single Responsibility Principle (SRP)
- Open-Closed Principle (OCP)
- Liskov Substitution Principle (LSP)
- Interface Segregation Principle (ISP)
- Dependency Inversion Principle (DIP)

### Single Responsibility Principle (SRP)

> Este principio nos dice que una clase debe tener una y solo una razón para cambiar - Robert C. Martin
- Una clase (o método) debe tener solo una responsabilidad o función.
Beneficios:
- Manteniblidad
- Reusabilidad incrementada
- Facilidad de testeo
- Escalabilidad
- Reducción de la complejidad de las partes que componen el sistema. 
> Hay que aumentar la cohesión y disminuir el acoplamiento

¿Cuando aplicarlo?
- Cuando hay varias razones para cambiar una clase o método.
- Cuando una clase o método tiene demasiadas responsabilidades.
- Alta complejidad y difícil mantenimiento.
- Dificultad para realizar pruebas unitarias.
- Duplicación de código. La responsabilidad no está bien definida.
