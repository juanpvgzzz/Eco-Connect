-- Publica la guía general en el piloto indicado con psql -v pilot_id=<UUID>.
-- Usa una cuenta administradora activa existente y conserva las ediciones posteriores.
with editor as (
    select id from users
    where pilot_id = :'pilot_id' and role = 'admin' and active
    order by created_at, id
    limit 1
), articles (slug, category, title, body) as (
    values
        ('separacion-en-casa', 'separation', 'Separa los residuos desde casa',
$text$En Colombia se usan tres colores para separar los residuos.

Verde para los orgánicos aprovechables, como las cáscaras de frutas y verduras. Blanco para los reciclables limpios y secos, como el papel, el cartón y las latas. Negro para los no aprovechables, como el papel higiénico y las servilletas usadas.

Separa los residuos al generarlos. Mantén los orgánicos lejos del papel y el cartón para que la humedad y la comida no los contaminen.$text$),
        ('restos-organicos-en-casa', 'separation', 'Cómo separar los residuos orgánicos',
$text$Aparta las cáscaras y restos de frutas y verduras, la borra de café y las hojas secas. Retira etiquetas, plásticos y otros empaques antes de guardarlos.

Usa un recipiente lavable con tapa para los restos de cocina y límpialo después de vaciarlo. Consulta qué residuos recibe tu programa antes de entregarlos, especialmente si tienes alimentos cocidos, carne o lácteos.$text$),
        ('reciclables-limpios-y-secos', 'materials', 'Prepara los reciclables limpios y secos',
$text$Separa el papel y el cartón secos de los envases reciclables, como botellas plásticas, frascos de vidrio y latas. Vacía los envases y, si tienen restos de comida o bebida, enjuágalos y déjalos secar.

Dobla las cajas limpias para ahorrar espacio. Mantén aparte el papel o el cartón manchado con grasa o comida. Consulta los materiales que acepta el servicio antes de entregarlos.$text$),
        ('habitos-para-generar-menos-residuos', 'materials', 'Buenas prácticas para generar menos residuos',
$text$Planea tus compras, aprovecha los alimentos que ya tienes y usa bolsas o recipientes reutilizables. Repara o dona objetos en buen estado antes de desecharlos.

Mantén aparte las pilas, los medicamentos vencidos y los aparatos eléctricos o electrónicos. Entrégalos en programas de recolección autorizados para cada tipo de residuo.$text$),
        ('compost-para-la-huerta', 'garden', 'Compostaje para la huerta',
$text$El compostaje transforma restos vegetales en un material que ayuda a mejorar el suelo. Para comenzar, combina cáscaras de frutas y verduras con hojas secas en un recipiente que permita la entrada de aire. Cubre cada aporte de cocina con hojas secas.

Mantén la mezcla húmeda como una esponja exprimida y revuélvela para que entre aire. Evita carne, pescado, lácteos, grasas y excrementos de mascotas en el compost casero.

Cuando el compost esté oscuro, suelto, huela a tierra y ya no se reconozcan los restos de comida, puedes incorporarlo al suelo de la huerta o las macetas.$text$)
)
insert into content_entries (pilot_id, author_id, slug, title, category, body, status, published_at)
select :'pilot_id', (select id from editor), :'pilot_id' || '-' || slug,
       title, category, body, 'publicado', now()
from articles
on conflict (slug) do nothing;
