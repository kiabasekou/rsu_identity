# apps/surveys/validators.py
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import Dict, List, Any, Tuple
import re
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class ResponseValidator:
    """Validateur de réponses selon type de question"""
    
    def __init__(self):
        self.validation_rules = {
            'TEXT': self._validate_text,
            'NUMBER': self._validate_number,
            'INTEGER': self._validate_integer,
            'SELECT': self._validate_select,
            'MULTISELECT': self._validate_multiselect,
            'BOOLEAN': self._validate_boolean,
            'DATE': self._validate_date,
            'DATETIME': self._validate_datetime,
            'GPS': self._validate_gps,
            'PHOTO': self._validate_photo,
            'AUDIO': self._validate_audio,
            'SIGNATURE': self._validate_signature,
        }
    
    def validate_response(self, question_config: Dict, response_value: Any) -> Dict:
        """Validation principale d'une réponse"""
        
        question_type = question_config.get('type')
        validator = self.validation_rules.get(question_type)
        
        if not validator:
            return {
                'valid': False,
                'errors': [f"Type de question non supporté: {question_type}"]
            }
        
        # Validation spécifique au type
        type_validation = validator(question_config, response_value)
        
        # Validation contraintes génériques
        constraint_validation = self._validate_constraints(question_config, response_value)
        
        # Fusion résultats
        all_errors = type_validation.get('errors', []) + constraint_validation.get('errors', [])
        
        return {
            'valid': len(all_errors) == 0,
            'errors': all_errors,
            'warnings': type_validation.get('warnings', []) + constraint_validation.get('warnings', [])
        }
    
    def _validate_text(self, config: Dict, value: Any) -> Dict:
        """Validation champ texte"""
        errors = []
        warnings = []
        
        if value is None or value == '':
            if config.get('required', False):
                errors.append("Champ texte obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        if not isinstance(value, str):
            errors.append("La valeur doit être du texte")
            return {'errors': errors, 'warnings': warnings}
        
        # Longueur
        min_length = config.get('min_length', 0)
        max_length = config.get('max_length', 1000)
        
        if len(value) < min_length:
            errors.append(f"Texte trop court: {len(value)} < {min_length}")
        
        if len(value) > max_length:
            errors.append(f"Texte trop long: {len(value)} > {max_length}")
        
        # Pattern regex si défini
        pattern = config.get('pattern')
        if pattern and not re.match(pattern, value):
            errors.append(f"Format invalide pour le pattern: {pattern}")
        
        # Détection contenu inapproprié
        inappropriate_words = ['test123', 'aaaaa', 'zzzzz']  # À étendre
        if any(word in value.lower() for word in inappropriate_words):
            warnings.append("Contenu potentiellement non valide détecté")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_number(self, config: Dict, value: Any) -> Dict:
        """Validation nombre décimal"""
        errors = []
        warnings = []
        
        if value is None:
            if config.get('required', False):
                errors.append("Nombre obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        try:
            num_value = Decimal(str(value))
        except (ValueError, TypeError):
            errors.append(f"Valeur non numérique: {value}")
            return {'errors': errors, 'warnings': warnings}
        
        # Plages
        min_value = config.get('min_value')
        max_value = config.get('max_value')
        
        if min_value is not None and num_value < Decimal(str(min_value)):
            errors.append(f"Valeur trop petite: {num_value} < {min_value}")
        
        if max_value is not None and num_value > Decimal(str(max_value)):
            errors.append(f"Valeur trop grande: {num_value} > {max_value}")
        
        # Détection valeurs suspectes
        if num_value == 0 and config.get('type_context') == 'revenue':
            warnings.append("Revenu de 0 peut être suspect")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_integer(self, config: Dict, value: Any) -> Dict:
        """Validation nombre entier"""
        errors = []
        warnings = []
        
        if value is None:
            if config.get('required', False):
                errors.append("Entier obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            errors.append(f"Valeur non entière: {value}")
            return {'errors': errors, 'warnings': warnings}
        
        # Vérifier que c'est bien un entier (pas un float)
        if isinstance(value, float) and value != int_value:
            errors.append("Valeur décimale non autorisée pour un entier")
        
        # Plages
        min_value = config.get('min_value')
        max_value = config.get('max_value')
        
        if min_value is not None and int_value < min_value:
            errors.append(f"Valeur trop petite: {int_value} < {min_value}")
        
        if max_value is not None and int_value > max_value:
            errors.append(f"Valeur trop grande: {int_value} > {max_value}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_select(self, config: Dict, value: Any) -> Dict:
        """Validation choix unique"""
        errors = []
        warnings = []
        
        if value is None or value == '':
            if config.get('required', False):
                errors.append("Sélection obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        valid_options = config.get('options', [])
        if not valid_options:
            errors.append("Aucune option définie pour ce choix")
            return {'errors': errors, 'warnings': warnings}
        
        # Extraire les valeurs valides
        valid_values = []
        for option in valid_options:
            if isinstance(option, dict):
                valid_values.append(option.get('value'))
            else:
                valid_values.append(option)
        
        if value not in valid_values:
            errors.append(f"Option invalide: {value}. Options valides: {valid_values}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_multiselect(self, config: Dict, value: Any) -> Dict:
        """Validation choix multiples"""
        errors = []
        warnings = []
        
        if value is None:
            value = []
        
        if not isinstance(value, list):
            errors.append("Les choix multiples doivent être une liste")
            return {'errors': errors, 'warnings': warnings}
        
        if len(value) == 0 and config.get('required', False):
            errors.append("Au moins une sélection obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        valid_options = config.get('options', [])
        valid_values = []
        for option in valid_options:
            if isinstance(option, dict):
                valid_values.append(option.get('value'))
            else:
                valid_values.append(option)
        
        for selected_value in value:
            if selected_value not in valid_values:
                errors.append(f"Option invalide: {selected_value}")
        
        # Contraintes de quantité
        min_selections = config.get('min_selections', 0)
        max_selections = config.get('max_selections', len(valid_values))
        
        if len(value) < min_selections:
            errors.append(f"Sélections insuffisantes: {len(value)} < {min_selections}")
        
        if len(value) > max_selections:
            errors.append(f"Trop de sélections: {len(value)} > {max_selections}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_boolean(self, config: Dict, value: Any) -> Dict:
        """Validation booléen"""
        errors = []
        warnings = []
        
        if value is None:
            if config.get('required', False):
                errors.append("Réponse Oui/Non obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        if not isinstance(value, bool):
            # Tentative de conversion
            if value in ['true', 'True', '1', 1, 'oui', 'Oui', 'yes', 'Yes']:
                value = True
            elif value in ['false', 'False', '0', 0, 'non', 'Non', 'no', 'No']:
                value = False
            else:
                errors.append(f"Valeur booléenne invalide: {value}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_date(self, config: Dict, value: Any) -> Dict:
        """Validation date"""
        errors = []
        warnings = []
        
        if value is None:
            if config.get('required', False):
                errors.append("Date obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        from datetime import datetime, date
        
        # Parsing de la date
        if isinstance(value, str):
            try:
                parsed_date = datetime.fromisoformat(value).date()
            except ValueError:
                try:
                    parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    errors.append(f"Format de date invalide: {value}")
                    return {'errors': errors, 'warnings': warnings}
        elif isinstance(value, datetime):
            parsed_date = value.date()
        elif isinstance(value, date):
            parsed_date = value
        else:
            errors.append(f"Type de date invalide: {type(value)}")
            return {'errors': errors, 'warnings': warnings}
        
        # Contraintes de date
        min_date = config.get('min_date')
        max_date = config.get('max_date')
        
        if min_date:
            if isinstance(min_date, str):
                min_date = datetime.fromisoformat(min_date).date()
            if parsed_date < min_date:
                errors.append(f"Date trop ancienne: {parsed_date} < {min_date}")
        
        if max_date:
            if isinstance(max_date, str):
                max_date = datetime.fromisoformat(max_date).date()
            if parsed_date > max_date:
                errors.append(f"Date trop récente: {parsed_date} > {max_date}")
        
        # Validations contextuelles
        today = timezone.now().date()
        
        # Date de naissance future
        if config.get('type_context') == 'birth_date' and parsed_date > today:
            errors.append("Date de naissance ne peut pas être dans le futur")
        
        # Date de naissance trop ancienne (>120 ans)
        if config.get('type_context') == 'birth_date':
            from dateutil.relativedelta import relativedelta
            min_birth_date = today - relativedelta(years=120)
            if parsed_date < min_birth_date:
                warnings.append("Date de naissance très ancienne (>120 ans)")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_gps(self, config: Dict, value: Any) -> Dict:
        """Validation coordonnées GPS"""
        errors = []
        warnings = []
        
        if value is None:
            if config.get('required', False):
                errors.append("Coordonnées GPS obligatoires")
            return {'errors': errors, 'warnings': warnings}
        
        if not isinstance(value, dict):
            errors.append("Coordonnées GPS doivent être un objet avec lat/lon")
            return {'errors': errors, 'warnings': warnings}
        
        latitude = value.get('lat')
        longitude = value.get('lon')
        accuracy = value.get('accuracy')
        
        # Validation latitude
        if latitude is None:
            errors.append("Latitude manquante")
        else:
            try:
                lat_float = float(latitude)
                if lat_float < -90 or lat_float > 90:
                    errors.append(f"Latitude invalide: {lat_float} (doit être entre -90 et 90)")
            except (ValueError, TypeError):
                errors.append(f"Latitude non numérique: {latitude}")
        
        # Validation longitude
        if longitude is None:
            errors.append("Longitude manquante")
        else:
            try:
                lon_float = float(longitude)
                if lon_float < -180 or lon_float > 180:
                    errors.append(f"Longitude invalide: {lon_float} (doit être entre -180 et 180)")
            except (ValueError, TypeError):
                errors.append(f"Longitude non numérique: {longitude}")
        
        # Validation précision
        if accuracy is not None:
            try:
                acc_float = float(accuracy)
                if acc_float < 0:
                    warnings.append("Précision GPS négative")
                elif acc_float > 100:
                    warnings.append(f"Précision GPS faible: {acc_float}m")
            except (ValueError, TypeError):
                warnings.append("Précision GPS non numérique")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_photo(self, config: Dict, value: Any) -> Dict:
        """Validation photo"""
        errors = []
        warnings = []
        
        if value is None or value == '':
            if config.get('required', False):
                errors.append("Photo obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        # Si c'est un chemin de fichier
        if isinstance(value, str):
            # Vérifier extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if not any(value.lower().endswith(ext) for ext in valid_extensions):
                errors.append(f"Extension de photo invalide. Extensions valides: {valid_extensions}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_audio(self, config: Dict, value: Any) -> Dict:
        """Validation audio"""
        errors = []
        warnings = []
        
        if value is None or value == '':
            if config.get('required', False):
                errors.append("Enregistrement audio obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        # Si c'est un chemin de fichier
        if isinstance(value, str):
            # Vérifier extension
            valid_extensions = ['.mp3', '.wav', '.aac', '.m4a']
            if not any(value.lower().endswith(ext) for ext in valid_extensions):
                errors.append(f"Extension audio invalide. Extensions valides: {valid_extensions}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_signature(self, config: Dict, value: Any) -> Dict:
        """Validation signature"""
        errors = []
        warnings = []
        
        if value is None or value == '':
            if config.get('required', False):
                errors.append("Signature obligatoire")
            return {'errors': errors, 'warnings': warnings}
        
        # Validation basique - à enrichir selon format signature
        if isinstance(value, str) and len(value) < 10:
            warnings.append("Signature très courte, vérifier la qualité")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_constraints(self, config: Dict, value: Any) -> Dict:
        """Validation contraintes génériques"""
        errors = []
        warnings = []
        
        # Contrainte de dépendance
        depends_on = config.get('depends_on')
        if depends_on and value is not None:
            # Logique de dépendance (nécessiterait le contexte de toutes les réponses)
            pass
        
        # Contrainte de logique métier
        business_rules = config.get('business_rules', [])
        for rule in business_rules:
            # Application des règles métier
            pass
        
        return {'errors': errors, 'warnings': warnings}


class LocationValidator:
    """Validateur de géolocalisation et cohérence géographique"""
    
    def __init__(self):
        # Définition des zones géographiques du Gabon
        self.gabon_bounds = {
            'min_lat': -4.0,
            'max_lat': 2.3,
            'min_lon': 8.5,
            'max_lon': 14.5
        }
        
        # Capitales provinciales du Gabon
        self.provincial_capitals = {
            'LIBREVILLE': {'lat': 0.4162, 'lon': 9.4673},
            'PORT_GENTIL': {'lat': -0.7193, 'lon': 8.7815},
            'FRANCEVILLE': {'lat': -1.6316, 'lon': 13.5833},
            'OYEM': {'lat': 1.5993, 'lon': 11.5794},
            'MOUILA': {'lat': -1.8639, 'lon': 11.0561},
            'LAMBARENE': {'lat': -0.7000, 'lon': 10.2414},
            'TCHIBANGA': {'lat': -2.8500, 'lon': 11.0167},
            'MAKOKOU': {'lat': 0.5738, 'lon': 12.8640},
            'GAMBA': {'lat': -2.6500, 'lon': 10.0000}
        }
    
    def validate_location_data(self, location_data: Dict, assigned_regions: List[str] = None) -> Dict:
        """Validation complète des données de géolocalisation"""
        
        errors = []
        warnings = []
        
        if not location_data:
            return {
                'valid': False,
                'errors': ['Données de géolocalisation manquantes'],
                'warnings': []
            }
        
        # Validation coordonnées GPS
        gps_validation = self._validate_gps_coordinates(location_data)
        errors.extend(gps_validation.get('errors', []))
        warnings.extend(gps_validation.get('warnings', []))
        
        # Validation dans les limites du Gabon
        gabon_validation = self._validate_within_gabon(location_data)
        errors.extend(gabon_validation.get('errors', []))
        warnings.extend(gabon_validation.get('warnings', []))
        
        # Validation cohérence région assignée
        if assigned_regions:
            region_validation = self._validate_assigned_region(location_data, assigned_regions)
            errors.extend(region_validation.get('errors', []))
            warnings.extend(region_validation.get('warnings', []))
        
        # Validation précision GPS
        accuracy_validation = self._validate_gps_accuracy(location_data)
        errors.extend(accuracy_validation.get('errors', []))
        warnings.extend(accuracy_validation.get('warnings', []))
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'location_analysis': self._analyze_location(location_data)
        }
    
    def _validate_gps_coordinates(self, location_data: Dict) -> Dict:
        """Validation basique des coordonnées GPS"""
        errors = []
        warnings = []
        
        lat = location_data.get('lat')
        lon = location_data.get('lon')
        
        if lat is None:
            errors.append("Latitude manquante")
        else:
            try:
                lat_float = float(lat)
                if lat_float < -90 or lat_float > 90:
                    errors.append(f"Latitude hors limites: {lat_float}")
            except (ValueError, TypeError):
                errors.append(f"Latitude invalide: {lat}")
        
        if lon is None:
            errors.append("Longitude manquante")
        else:
            try:
                lon_float = float(lon)
                if lon_float < -180 or lon_float > 180:
                    errors.append(f"Longitude hors limites: {lon_float}")
            except (ValueError, TypeError):
                errors.append(f"Longitude invalide: {lon}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_within_gabon(self, location_data: Dict) -> Dict:
        """Validation que les coordonnées sont dans les limites du Gabon"""
        errors = []
        warnings = []
        
        try:
            lat = float(location_data.get('lat'))
            lon = float(location_data.get('lon'))
            
            # Vérifier dans les limites approximatives du Gabon
            if not (self.gabon_bounds['min_lat'] <= lat <= self.gabon_bounds['max_lat']):
                errors.append(f"Latitude hors du Gabon: {lat}")
            
            if not (self.gabon_bounds['min_lon'] <= lon <= self.gabon_bounds['max_lon']):
                errors.append(f"Longitude hors du Gabon: {lon}")
            
            # Zone maritime (cas particuliers)
            if lat < -3.5 and lon < 10:
                warnings.append("Position en zone maritime, vérifier la précision")
            
        except (ValueError, TypeError):
            # Erreurs déjà catchées dans _validate_gps_coordinates
            pass
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_assigned_region(self, location_data: Dict, assigned_regions: List[str]) -> Dict:
        """Validation cohérence avec les régions assignées à l'enquêteur"""
        errors = []
        warnings = []
        
        try:
            lat = float(location_data.get('lat'))
            lon = float(location_data.get('lon'))
            
            # Déterminer la région approximative basée sur les coordonnées
            detected_region = self._detect_region_from_coordinates(lat, lon)
            
            if detected_region and detected_region not in assigned_regions:
                errors.append(
                    f"Région détectée ({detected_region}) non assignée à l'enquêteur. "
                    f"Régions assignées: {', '.join(assigned_regions)}"
                )
            
        except (ValueError, TypeError):
            pass
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_gps_accuracy(self, location_data: Dict) -> Dict:
        """Validation de la précision GPS"""
        errors = []
        warnings = []
        
        accuracy = location_data.get('accuracy')
        
        if accuracy is None:
            warnings.append("Précision GPS non fournie")
            return {'errors': errors, 'warnings': warnings}
        
        try:
            accuracy_float = float(accuracy)
            
            if accuracy_float < 0:
                errors.append("Précision GPS négative")
            elif accuracy_float > 100:
                errors.append(f"Précision GPS insuffisante: {accuracy_float}m (max 100m)")
            elif accuracy_float > 50:
                warnings.append(f"Précision GPS modérée: {accuracy_float}m")
            elif accuracy_float > 20:
                warnings.append(f"Précision GPS acceptable: {accuracy_float}m")
            
        except (ValueError, TypeError):
            warnings.append("Précision GPS non numérique")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _detect_region_from_coordinates(self, lat: float, lon: float) -> str:
        """Détection approximative de la région basée sur les coordonnées"""
        
        # Calcul distance aux capitales provinciales
        min_distance = float('inf')
        closest_region = None
        
        for region, coords in self.provincial_capitals.items():
            distance = self._calculate_distance(lat, lon, coords['lat'], coords['lon'])
            if distance < min_distance:
                min_distance = distance
                closest_region = region
        
        # Retourner la région si suffisamment proche (< 200km)
        if min_distance < 200:
            return closest_region
        
        return None
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcul distance haversine entre deux points GPS"""
        import math
        
        # Rayon de la Terre en km
        R = 6371.0
        
        # Conversion en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Différences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Formule haversine
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _analyze_location(self, location_data: Dict) -> Dict:
        """Analyse contextuelle de la localisation"""
        analysis = {
            'region_detected': None,
            'nearest_city': None,
            'environment_type': None,
            'distance_to_capital': None
        }
        
        try:
            lat = float(location_data.get('lat'))
            lon = float(location_data.get('lon'))
            
            # Région détectée
            analysis['region_detected'] = self._detect_region_from_coordinates(lat, lon)
            
            # Ville la plus proche
            analysis['nearest_city'] = analysis['region_detected']
            
            # Type d'environnement (urbain/rural basé sur distance aux capitales)
            min_distance_to_capital = min(
                self._calculate_distance(lat, lon, coords['lat'], coords['lon'])
                for coords in self.provincial_capitals.values()
            )
            
            analysis['distance_to_capital'] = round(min_distance_to_capital, 2)
            
            if min_distance_to_capital < 20:
                analysis['environment_type'] = 'URBAN'
            elif min_distance_to_capital < 50:
                analysis['environment_type'] = 'PERI_URBAN'
            else:
                analysis['environment_type'] = 'RURAL'
            
        except (ValueError, TypeError):
            pass
        
        return analysis


class ConsistencyValidator:
    """Validateur de cohérence entre réponses"""
    
    def __init__(self):
        self.consistency_rules = [
            self._validate_age_birth_year_consistency,
            self._validate_household_composition_consistency,
            self._validate_income_employment_consistency,
            self._validate_education_age_consistency,
            self._validate_marital_age_consistency
        ]
    
    def validate_response_consistency(self, all_responses: Dict) -> Dict:
        """Validation de cohérence globale des réponses"""
        
        errors = []
        warnings = []
        
        for rule in self.consistency_rules:
            try:
                result = rule(all_responses)
                errors.extend(result.get('errors', []))
                warnings.extend(result.get('warnings', []))
            except Exception as e:
                logger.error(f"Erreur dans règle de cohérence {rule.__name__}: {e}")
                warnings.append(f"Erreur validation cohérence: {rule.__name__}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def apply_rule(self, rule_config: Dict, responses: Dict) -> Dict:
        """Application d'une règle de cohérence configurée"""
        
        rule_type = rule_config.get('type')
        
        if rule_type == 'CROSS_FIELD_VALIDATION':
            return self._apply_cross_field_rule(rule_config, responses)
        elif rule_type == 'LOGICAL_CONSISTENCY':
            return self._apply_logical_consistency_rule(rule_config, responses)
        elif rule_type == 'RANGE_CONSISTENCY':
            return self._apply_range_consistency_rule(rule_config, responses)
        else:
            return {'passed': True, 'errors': [], 'warnings': []}
    
    def _validate_age_birth_year_consistency(self, responses: Dict) -> Dict:
        """Validation cohérence âge et année de naissance"""
        errors = []
        warnings = []
        
        age = responses.get('age')
        birth_year = responses.get('birth_year')
        birth_date = responses.get('birth_date')
        
        current_year = timezone.now().year
        
        # Validation âge vs année naissance
        if age is not None and birth_year is not None:
            try:
                age_int = int(age)
                birth_year_int = int(birth_year)
                calculated_age = current_year - birth_year_int
                
                # Tolérance de ±1 an
                if abs(age_int - calculated_age) > 1:
                    errors.append(
                        f"Incohérence âge/année naissance: âge={age_int}, "
                        f"année={birth_year_int}, âge calculé={calculated_age}"
                    )
            except (ValueError, TypeError):
                warnings.append("Âge ou année de naissance non numérique")
        
        # Validation date de naissance complète
        if birth_date and age is not None:
            try:
                from datetime import datetime
                if isinstance(birth_date, str):
                    birth_dt = datetime.fromisoformat(birth_date)
                else:
                    birth_dt = birth_date
                
                from dateutil.relativedelta import relativedelta
                calculated_age = relativedelta(timezone.now(), birth_dt).years
                age_int = int(age)
                
                if abs(age_int - calculated_age) > 1:
                    errors.append(
                        f"Incohérence âge/date naissance: âge={age_int}, "
                        f"date={birth_date}, âge calculé={calculated_age}"
                    )
            except Exception:
                warnings.append("Erreur calcul âge depuis date de naissance")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_household_composition_consistency(self, responses: Dict) -> Dict:
        """Validation cohérence composition du ménage"""
        errors = []
        warnings = []
        
        household_size = responses.get('household_size')
        adults_count = responses.get('adults_count')
        children_count = responses.get('children_count')
        elderly_count = responses.get('elderly_count')
        
        if household_size is not None:
            try:
                total_size = int(household_size)
                
                # Calcul total déclaré par catégories
                declared_total = 0
                if adults_count is not None:
                    declared_total += int(adults_count)
                if children_count is not None:
                    declared_total += int(children_count)
                if elderly_count is not None:
                    declared_total += int(elderly_count)
                
                # Vérifier cohérence si toutes catégories renseignées
                if adults_count is not None and children_count is not None:
                    if abs(total_size - declared_total) > 0:
                        errors.append(
                            f"Incohérence taille ménage: total={total_size}, "
                            f"adultes+enfants+âgés={declared_total}"
                        )
                
                # Validation logique
                if total_size < 1:
                    errors.append("Taille de ménage doit être ≥ 1")
                
                if total_size > 20:
                    warnings.append(f"Taille de ménage très importante: {total_size}")
                
            except (ValueError, TypeError):
                warnings.append("Valeurs de composition ménage non numériques")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_income_employment_consistency(self, responses: Dict) -> Dict:
        """Validation cohérence revenus et statut emploi"""
        errors = []
        warnings = []
        
        monthly_income = responses.get('monthly_income')
        employment_status = responses.get('employment_status')
        profession = responses.get('profession')
        
        if monthly_income is not None and employment_status is not None:
            try:
                income_amount = float(monthly_income)
                
                # Chômeur avec revenus élevés
                if employment_status == 'UNEMPLOYED' and income_amount > 50000:
                    errors.append(
                        f"Incohérence: chômeur avec revenus élevés ({income_amount} FCFA)"
                    )
                
                # Employé sans revenus
                if employment_status in ['EMPLOYED', 'SELF_EMPLOYED'] and income_amount <= 0:
                    errors.append(
                        f"Incohérence: employé sans revenus (statut: {employment_status})"
                    )
                
                # Retraité avec revenus professionnels élevés
                if employment_status == 'RETIRED' and income_amount > 200000:
                    warnings.append(
                        f"Revenus élevés pour retraité: {income_amount} FCFA"
                    )
                
                # Étudiant avec revenus professionnels
                if employment_status == 'STUDENT' and income_amount > 100000:
                    warnings.append(
                        f"Revenus élevés pour étudiant: {income_amount} FCFA"
                    )
                
            except (ValueError, TypeError):
                warnings.append("Revenus non numériques")
        
        # Validation profession vs statut emploi
        if profession and employment_status:
            if employment_status == 'UNEMPLOYED' and profession not in ['', 'NONE', 'SANS_EMPLOI']:
                warnings.append(
                    f"Profession renseignée ({profession}) alors que statut chômeur"
                )
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_education_age_consistency(self, responses: Dict) -> Dict:
        """Validation cohérence éducation et âge"""
        errors = []
        warnings = []
        
        age = responses.get('age')
        education_level = responses.get('education_level')
        currently_studying = responses.get('currently_studying')
        
        if age is not None and education_level is not None:
            try:
                age_int = int(age)
                
                # Validation niveaux éducation vs âge
                education_age_mapping = {
                    'NO_EDUCATION': {'min_age': 0, 'typical_max': 99},
                    'PRIMARY_INCOMPLETE': {'min_age': 6, 'typical_max': 15},
                    'PRIMARY_COMPLETE': {'min_age': 11, 'typical_max': 99},
                    'SECONDARY_INCOMPLETE': {'min_age': 12, 'typical_max': 18},
                    'SECONDARY_COMPLETE': {'min_age': 17, 'typical_max': 99},
                    'UNIVERSITY_INCOMPLETE': {'min_age': 18, 'typical_max': 25},
                    'UNIVERSITY_COMPLETE': {'min_age': 21, 'typical_max': 99},
                    'POSTGRADUATE': {'min_age': 23, 'typical_max': 99}
                }
                
                mapping = education_age_mapping.get(education_level)
                if mapping:
                    if age_int < mapping['min_age']:
                        errors.append(
                            f"Âge trop jeune pour niveau éducation: {age_int} ans "
                            f"pour {education_level} (min {mapping['min_age']} ans)"
                        )
                
                # Validations spécifiques
                if education_level == 'POSTGRADUATE' and age_int < 23:
                    errors.append("Âge trop jeune pour études supérieures")
                
                if education_level == 'NO_EDUCATION' and age_int > 80:
                    warnings.append("Pas d'éducation à un âge avancé - vérifier")
                
            except (ValueError, TypeError):
                warnings.append("Âge non numérique pour validation éducation")
        
        # Validation études en cours vs âge
        if currently_studying and age is not None:
            try:
                age_int = int(age)
                if age_int > 40:
                    warnings.append(f"Études en cours à {age_int} ans - vérifier")
            except (ValueError, TypeError):
                pass
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_marital_age_consistency(self, responses: Dict) -> Dict:
        """Validation cohérence statut marital et âge"""
        errors = []
        warnings = []
        
        age = responses.get('age')
        marital_status = responses.get('marital_status')
        children_count = responses.get('children_count')
        
        if age is not None and marital_status is not None:
            try:
                age_int = int(age)
                
                # Marié très jeune
                if marital_status in ['MARRIED', 'DIVORCED', 'WIDOWED'] and age_int < 16:
                    warnings.append(
                        f"Statut marital {marital_status} à {age_int} ans - vérifier"
                    )
                
                # Divorcé/veuf très jeune
                if marital_status in ['DIVORCED', 'WIDOWED'] and age_int < 18:
                    warnings.append(
                        f"Statut {marital_status} très jeune: {age_int} ans"
                    )
                
                # Célibataire avec enfants
                if marital_status == 'SINGLE' and children_count is not None:
                    try:
                        children_int = int(children_count)
                        if children_int > 0:
                            warnings.append(
                                f"Célibataire avec {children_int} enfant(s) - situation particulière"
                            )
                    except (ValueError, TypeError):
                        pass
                
            except (ValueError, TypeError):
                warnings.append("Âge non numérique pour validation statut marital")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _apply_cross_field_rule(self, rule_config: Dict, responses: Dict) -> Dict:
        """Application règle de validation croisée"""
        
        field_a = rule_config.get('field_a')
        field_b = rule_config.get('field_b')
        operator = rule_config.get('operator')
        
        value_a = responses.get(field_a)
        value_b = responses.get(field_b)
        
        if value_a is None or value_b is None:
            return {'passed': True, 'errors': [], 'warnings': []}
        
        try:
            # Validation selon opérateur
            if operator == 'GREATER_THAN':
                passed = float(value_a) > float(value_b)
            elif operator == 'LESS_THAN':
                passed = float(value_a) < float(value_b)
            elif operator == 'EQUAL':
                passed = value_a == value_b
            elif operator == 'NOT_EQUAL':
                passed = value_a != value_b
            else:
                return {'passed': True, 'errors': [], 'warnings': []}
            
            if not passed:
                error_msg = f"Règle de cohérence échouée: {field_a} {operator} {field_b}"
                return {'passed': False, 'errors': [error_msg], 'warnings': []}
            
        except (ValueError, TypeError):
            warning_msg = f"Impossible de comparer {field_a} et {field_b}"
            return {'passed': True, 'errors': [], 'warnings': [warning_msg]}
        
        return {'passed': True, 'errors': [], 'warnings': []}
    
    def _apply_logical_consistency_rule(self, rule_config: Dict, responses: Dict) -> Dict:
        """Application règle de cohérence logique"""
        
        condition = rule_config.get('condition')
        consequence = rule_config.get('consequence')
        
        # Évaluation condition
        condition_met = self._evaluate_condition(condition, responses)
        
        if condition_met:
            # Vérifier conséquence
            consequence_met = self._evaluate_condition(consequence, responses)
            
            if not consequence_met:
                error_msg = f"Règle logique échouée: si {condition['description']} alors {consequence['description']}"
                return {'passed': False, 'errors': [error_msg], 'warnings': []}
        
        return {'passed': True, 'errors': [], 'warnings': []}
    
    def _apply_range_consistency_rule(self, rule_config: Dict, responses: Dict) -> Dict:
        """Application règle de cohérence de plage"""
        
        field = rule_config.get('field')
        min_value = rule_config.get('min_value')
        max_value = rule_config.get('max_value')
        context_fields = rule_config.get('context_fields', [])
        
        value = responses.get(field)
        if value is None:
            return {'passed': True, 'errors': [], 'warnings': []}
        
        try:
            numeric_value = float(value)
            
            # Ajustement plages selon contexte
            adjusted_min = min_value
            adjusted_max = max_value
            
            for context_field in context_fields:
                context_value = responses.get(context_field)
                if context_value:
                    # Logique d'ajustement selon contexte
                    # Par exemple: ajuster plage revenus selon région
                    pass
            
            if adjusted_min is not None and numeric_value < adjusted_min:
                error_msg = f"Valeur {field} trop basse: {numeric_value} < {adjusted_min}"
                return {'passed': False, 'errors': [error_msg], 'warnings': []}
            
            if adjusted_max is not None and numeric_value > adjusted_max:
                error_msg = f"Valeur {field} trop élevée: {numeric_value} > {adjusted_max}"
                return {'passed': False, 'errors': [error_msg], 'warnings': []}
            
        except (ValueError, TypeError):
            warning_msg = f"Valeur non numérique pour {field}: {value}"
            return {'passed': True, 'errors': [], 'warnings': [warning_msg]}
        
        return {'passed': True, 'errors': [], 'warnings': []}
    
    def _evaluate_condition(self, condition: Dict, responses: Dict) -> bool:
        """Évaluation d'une condition logique"""
        
        field = condition.get('field')
        operator = condition.get('operator')
        expected_value = condition.get('value')
        
        actual_value = responses.get(field)
        
        if actual_value is None:
            return False
        
        try:
            if operator == 'EQUALS':
                return actual_value == expected_value
            elif operator == 'NOT_EQUALS':
                return actual_value != expected_value
            elif operator == 'GREATER_THAN':
                return float(actual_value) > float(expected_value)
            elif operator == 'LESS_THAN':
                return float(actual_value) < float(expected_value)
            elif operator == 'IN':
                return actual_value in expected_value
            elif operator == 'NOT_IN':
                return actual_value not in expected_value
            else:
                return False
        except (ValueError, TypeError):
            return False